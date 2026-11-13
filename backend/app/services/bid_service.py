import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AuctionEvent,
    Bid,
    BritishAuctionConfig,
    RFQ,
    RFQSupplier,
    Supplier,
)
from app.models.enums import (
    AuctionEventType,
    AuctionStatus,
    AuctionType,
    ExtensionTrigger,
)
from app.schemas.bid import BidCreate, BidRecord, BidSubmissionResult
from app.services.auction_engine import (
    compute_extension,
    compute_ranking,
    derive_status,
    evaluate_trigger,
    generate_extension_reason,
    in_trigger_window,
)
from app.services.clock import Clock
from app.services.lifecycle_service import ensure_lifecycle_events


class RFQNotFoundError(Exception):
    def __init__(self, rfq_id: UUID | str):
        super().__init__(f"RFQ with id {rfq_id} was not found.")
        self.rfq_id = rfq_id


class SupplierNotFoundError(Exception):
    def __init__(self, supplier_id: UUID | str):
        super().__init__(f"Supplier with id {supplier_id} was not found.")
        self.supplier_id = supplier_id


class SupplierNotInvitedError(Exception):
    def __init__(self, rfq_id: UUID | str, supplier_id: UUID | str):
        super().__init__(f"Supplier {supplier_id} is not invited to RFQ {rfq_id}.")
        self.rfq_id = rfq_id
        self.supplier_id = supplier_id


class AuctionNotStartedError(Exception):
    def __init__(self, rfq_id: UUID | str, start_time: datetime, now: datetime):
        super().__init__(f"Auction {rfq_id} has not started yet (starts at {start_time.isoformat()}).")
        self.rfq_id = rfq_id
        self.start_time = start_time
        self.now = now


class AuctionClosedError(Exception):
    def __init__(self, rfq_id: UUID | str, close_time: datetime, now: datetime, forced: bool = False):
        status_name = "force-closed" if forced else "closed"
        super().__init__(f"Auction {rfq_id} is {status_name} (closed at {close_time.isoformat()}).")
        self.rfq_id = rfq_id
        self.close_time = close_time
        self.now = now
        self.forced = forced


class BidNotLowerError(Exception):
    def __init__(self, previous_best: Decimal, attempted_bid: Decimal):
        super().__init__(
            f"Bid must be strictly lower than your previous best ({previous_best:.2f}). Attempted: {attempted_bid:.2f}."
        )
        self.previous_best = previous_best
        self.attempted_bid = attempted_bid


class IdempotencyKeyConflictError(Exception):
    def __init__(self, idempotency_key: str):
        super().__init__(f"Idempotency key '{idempotency_key}' was previously used with a different bid payload.")
        self.idempotency_key = idempotency_key


def compute_request_hash(
    supplier_id: UUID | str,
    freight_charges: Decimal,
    origin_charges: Decimal,
    destination_charges: Decimal,
    transit_time_days: int,
    quote_validity_days: int,
) -> str:
    """Computes SHA-256 hash of canonical JSON payload for idempotency comparison."""
    canonical_dict = {
        "destination_charges": str(Decimal(str(destination_charges)).quantize(Decimal("0.01"))),
        "freight_charges": str(Decimal(str(freight_charges)).quantize(Decimal("0.01"))),
        "origin_charges": str(Decimal(str(origin_charges)).quantize(Decimal("0.01"))),
        "quote_validity_days": int(quote_validity_days),
        "supplier_id": str(supplier_id),
        "transit_time_days": int(transit_time_days),
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def submit_bid(
    rfq_id: UUID,
    bid_in: BidCreate,
    session: Session,
    clock: Clock,
    idempotency_key: Optional[str] = None,
) -> Tuple[BidSubmissionResult, bool]:
    """
    Submits a quote under the 13-step transactional algorithm.
    Returns (result, is_idempotent_replay).
    """
    now = clock.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Truncate/validate idempotency key length if provided
    if idempotency_key and len(idempotency_key) > 64:
        raise ValueError("Idempotency-Key header must not exceed 64 characters.")

    # 2. SELECT rfq FOR UPDATE (serializes bids per RFQ row)
    # SQLite doesn't support SELECT ... FOR UPDATE with_for_update(), so dialect-check
    stmt = select(RFQ).where(RFQ.id == rfq_id)
    if session.bind and session.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()

    rfq = session.execute(stmt).scalar_one_or_none()
    if not rfq:
        raise RFQNotFoundError(rfq_id)

    # 3. Idempotency check if key is provided
    calculated_hash: Optional[str] = None
    if idempotency_key:
        calculated_hash = compute_request_hash(
            supplier_id=bid_in.supplier_id,
            freight_charges=bid_in.freight_charges,
            origin_charges=bid_in.origin_charges,
            destination_charges=bid_in.destination_charges,
            transit_time_days=bid_in.transit_time_days,
            quote_validity_days=bid_in.quote_validity_days,
        )

        existing_bid = session.execute(
            select(Bid).where(
                Bid.rfq_id == rfq_id,
                Bid.supplier_id == bid_in.supplier_id,
                Bid.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

        if existing_bid:
            if existing_bid.request_hash == calculated_hash:
                # Same payload -> return cached snapshot directly without state check
                snapshot = existing_bid.result_snapshot
                if snapshot:
                    result = BidSubmissionResult.model_validate(snapshot)
                    return result, True
            else:
                raise IdempotencyKeyConflictError(idempotency_key)

    # 4. Run idempotent lifecycle catch-up under the row lock
    ensure_lifecycle_events(rfq, now, session)

    # 5. Derive current status strictly from timestamps; reject if not ACTIVE
    derived_status = derive_status(
        bid_start_time=rfq.bid_start_time,
        current_close_time=rfq.current_close_time,
        forced_close_time=rfq.forced_close_time,
        now=now,
    )
    if derived_status == AuctionStatus.SCHEDULED:
        raise AuctionNotStartedError(rfq_id, rfq.bid_start_time, now)
    elif derived_status in (AuctionStatus.CLOSED, AuctionStatus.FORCE_CLOSED):
        raise AuctionClosedError(
            rfq_id,
            rfq.current_close_time,
            now,
            forced=(derived_status == AuctionStatus.FORCE_CLOSED),
        )

    # 6. Verify supplier is invited to this RFQ
    invitation = session.execute(
        select(RFQSupplier).where(
            RFQSupplier.rfq_id == rfq_id,
            RFQSupplier.supplier_id == bid_in.supplier_id,
        )
    ).scalar_one_or_none()
    if not invitation:
        raise SupplierNotInvitedError(rfq_id, bid_in.supplier_id)

    # 7. Fetch carrier name snapshot from suppliers table
    supplier = session.execute(
        select(Supplier).where(Supplier.id == bid_in.supplier_id)
    ).scalar_one_or_none()
    if not supplier:
        raise SupplierNotFoundError(bid_in.supplier_id)
    carrier_name_snapshot = supplier.name

    # 8. Compute total price and ensure strictly lower than supplier's previous best
    total_price = bid_in.freight_charges + bid_in.origin_charges + bid_in.destination_charges

    existing_supplier_bids = session.execute(
        select(Bid).where(
            Bid.rfq_id == rfq_id,
            Bid.supplier_id == bid_in.supplier_id,
        )
    ).scalars().all()

    if existing_supplier_bids:
        previous_best = min(b.total_price for b in existing_supplier_bids)
        if total_price >= previous_best:
            raise BidNotLowerError(previous_best=previous_best, attempted_bid=total_price)

    # 9. Compute ranking BEFORE inserting this bid
    all_bids_stmt = select(Bid).where(Bid.rfq_id == rfq_id)
    all_bids_before = session.execute(all_bids_stmt).scalars().all()
    ranking_before = compute_ranking(all_bids_before)

    # 10. Insert the new bid
    new_bid = Bid(
        rfq_id=rfq_id,
        supplier_id=bid_in.supplier_id,
        carrier_name=carrier_name_snapshot,
        freight_charges=bid_in.freight_charges,
        origin_charges=bid_in.origin_charges,
        destination_charges=bid_in.destination_charges,
        total_price=total_price,
        transit_time_days=bid_in.transit_time_days,
        quote_validity_days=bid_in.quote_validity_days,
        submitted_at=now,
        idempotency_key=idempotency_key,
        request_hash=calculated_hash,
    )
    session.add(new_bid)
    session.flush()

    # 11. Compute ranking AFTER inserting this bid
    all_bids_after = list(all_bids_before) + [new_bid]
    ranking_after = compute_ranking(all_bids_after)

    # Find the new rank of this supplier
    supplier_rank_record = next(
        (r for r in ranking_after if str(r.supplier_id) == str(bid_in.supplier_id)),
        None,
    )
    supplier_new_rank = supplier_rank_record.rank if supplier_rank_record else 1

    # 12. British Auction Extension Evaluation
    was_extended = False
    new_close_time = rfq.current_close_time
    extension_reason: Optional[str] = None

    if rfq.auction_type == AuctionType.BRITISH:
        config = session.execute(
            select(BritishAuctionConfig).where(BritishAuctionConfig.rfq_id == rfq_id)
        ).scalar_one_or_none()

        if config:
            in_window = in_trigger_window(
                current_close_time=rfq.current_close_time,
                trigger_window_minutes=config.trigger_window_minutes,
                now=now,
            )

            if in_window:
                is_triggered = evaluate_trigger(
                    trigger_type=config.extension_trigger,
                    ranking_before=ranking_before,
                    ranking_after=ranking_after,
                    new_bid=new_bid,
                )

                if is_triggered:
                    old_close = rfq.current_close_time
                    computed_new_close, extended = compute_extension(
                        current_close_time=rfq.current_close_time,
                        extension_minutes=config.extension_minutes,
                        forced_close_time=rfq.forced_close_time,
                    )

                    previous_l1_name = ranking_before[0].carrier_name if ranking_before else None

                    if extended:
                        rfq.current_close_time = computed_new_close
                        new_close_time = computed_new_close
                        was_extended = True
                        extension_reason = generate_extension_reason(
                            trigger_type=config.extension_trigger,
                            current_l1_name=carrier_name_snapshot,
                            previous_l1_name=previous_l1_name,
                            occurred_at=now,
                            old_close=old_close,
                            new_close=computed_new_close,
                            window_minutes=config.trigger_window_minutes,
                        )

                        # Write TIME_EXTENDED event
                        ext_event = AuctionEvent(
                            rfq_id=rfq_id,
                            event_type=AuctionEventType.TIME_EXTENDED,
                            bid_id=new_bid.id,
                            payload={
                                "trigger_type": config.extension_trigger.value,
                                "old_close": old_close.isoformat(),
                                "new_close": computed_new_close.isoformat(),
                                "extension_minutes": config.extension_minutes,
                                "bid_id": str(new_bid.id),
                            },
                            reason=extension_reason,
                            occurred_at=now,
                            created_at=now,
                            is_recovered=False,
                        )
                        session.add(ext_event)
                    else:
                        # Extension skipped because current close is already at forced close
                        skip_reason = (
                            f"Extension skipped for RFQ '{rfq.name}': close time {old_close.strftime('%I:%M %p')} "
                            f"is already capped at Forced Bid Close Time ({rfq.forced_close_time.strftime('%I:%M %p')})."
                        )
                        skip_event = AuctionEvent(
                            rfq_id=rfq_id,
                            event_type=AuctionEventType.EXTENSION_SKIPPED_AT_FORCED_CLOSE,
                            bid_id=new_bid.id,
                            payload={
                                "trigger_type": config.extension_trigger.value,
                                "forced_close": rfq.forced_close_time.isoformat(),
                                "bid_id": str(new_bid.id),
                            },
                            reason=skip_reason,
                            occurred_at=now,
                            created_at=now,
                            is_recovered=False,
                        )
                        session.add(skip_event)

    # 13. Write BID_PLACED event
    rank_before_num = next((r.rank for r in ranking_before if str(r.supplier_id) == str(bid_in.supplier_id)), None)
    bid_placed_reason = (
        f"{carrier_name_snapshot} submitted bid for {total_price:.2f} {rfq.currency} "
        f"(rank {rank_before_num or 'new'} → {supplier_new_rank})."
    )
    bid_event = AuctionEvent(
        rfq_id=rfq_id,
        event_type=AuctionEventType.BID_PLACED,
        bid_id=new_bid.id,
        payload={
            "bid_id": str(new_bid.id),
            "supplier_id": str(bid_in.supplier_id),
            "supplier_name": carrier_name_snapshot,
            "total_price": str(total_price),
            "rank_before": rank_before_num,
            "rank_after": supplier_new_rank,
            "extended": was_extended,
        },
        reason=bid_placed_reason,
        occurred_at=now,
        created_at=now,
        is_recovered=False,
    )
    session.add(bid_event)

    # 14. Build snapshot and persist on bid row for idempotency replay
    bid_record = BidRecord.model_validate(new_bid)
    result = BidSubmissionResult(
        bid=bid_record,
        rank=supplier_new_rank,
        extended=was_extended,
        new_close_time=new_close_time,
        extension_reason=extension_reason,
        server_time=now,
    )
    new_bid.result_snapshot = json.loads(result.model_dump_json())

    session.commit()
    return result, False
