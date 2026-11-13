from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.entities import AuctionEvent, RFQ
from app.models.enums import AuctionEventType
from app.services.auction_engine import derive_status, due_lifecycle_events


def ensure_lifecycle_events(rfq: RFQ, now: datetime, session: Session) -> list[AuctionEvent]:
    """
    Idempotent lifecycle event recorder and status cache updater.
    Computes any due lifecycle transitions (AUCTION_STARTED, AUCTION_CLOSED, AUCTION_FORCE_CLOSED)
    that are missing and writes them in chronological order with their logical occurred_at.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Fetch existing lifecycle event types for this RFQ
    stmt = select(AuctionEvent.event_type).where(
        AuctionEvent.rfq_id == rfq.id,
        AuctionEvent.event_type.in_([
            AuctionEventType.AUCTION_STARTED,
            AuctionEventType.AUCTION_CLOSED,
            AuctionEventType.AUCTION_FORCE_CLOSED,
        ]),
    )
    existing_types = set(session.execute(stmt).scalars().all())

    # 2. Compute due events using pure engine logic
    due = due_lifecycle_events(
        bid_start_time=rfq.bid_start_time,
        current_close_time=rfq.current_close_time,
        forced_close_time=rfq.forced_close_time,
        existing_event_types=existing_types,
        now=now,
    )

    created_events: list[AuctionEvent] = []
    for event_type, occurred_at in due:
        # If created > 5s after occurred_at, flag as recovered
        diff = (now - occurred_at).total_seconds()
        is_recovered = diff > 5.0

        if event_type == AuctionEventType.AUCTION_STARTED:
            reason = f"Auction '{rfq.name}' bidding opened at {occurred_at.strftime('%I:%M:%S %p')} UTC."
            payload = {"rfq_id": str(rfq.id), "name": rfq.name}
        elif event_type == AuctionEventType.AUCTION_FORCE_CLOSED:
            reason = f"Auction '{rfq.name}' reached forced close time and closed at {occurred_at.strftime('%I:%M:%S %p')} UTC."
            payload = {"rfq_id": str(rfq.id), "forced_close_time": occurred_at.isoformat()}
        else:
            reason = f"Auction '{rfq.name}' closed at {occurred_at.strftime('%I:%M:%S %p')} UTC."
            payload = {"rfq_id": str(rfq.id), "close_time": occurred_at.isoformat()}

        event = AuctionEvent(
            rfq_id=rfq.id,
            event_type=event_type,
            bid_id=None,
            payload=payload,
            reason=reason,
            occurred_at=occurred_at,
            created_at=now,
            is_recovered=is_recovered,
        )
        session.add(event)
        created_events.append(event)

    # 3. Update the cached status column
    new_derived_status = derive_status(
        bid_start_time=rfq.bid_start_time,
        current_close_time=rfq.current_close_time,
        forced_close_time=rfq.forced_close_time,
        now=now,
    )
    if rfq.status != new_derived_status:
        rfq.status = new_derived_status

    session.flush()
    return created_events

