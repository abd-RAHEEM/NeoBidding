from datetime import timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_db
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
)
from app.schemas.bid import (
    BidCreate,
    BidHistoryListResponse,
    BidRecord,
    BidSubmissionResult,
)
from app.schemas.event import AuctionEventItem, AuctionEventListResponse
from app.schemas.rfq import (
    BritishConfigSchema,
    RFQCreate,
    RFQDetailResponse,
    RFQListItem,
    RFQListResponse,
    RFQStats,
    SupplierRankDetail,
)
from app.schemas.supplier import SupplierResponse
from app.services.auction_engine import compute_ranking, derive_status
from app.services.bid_service import (
    AuctionClosedError,
    AuctionNotStartedError,
    BidNotLowerError,
    IdempotencyKeyConflictError,
    RFQNotFoundError,
    SupplierNotFoundError,
    SupplierNotInvitedError,
    submit_bid,
)
from app.services.clock import Clock

router = APIRouter()


@router.post("/rfqs", response_model=RFQDetailResponse, status_code=status.HTTP_201_CREATED, tags=["RFQs"])
def create_rfq(
    payload: RFQCreate,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    now = clock.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Check unique reference_id
    existing_ref = db.execute(select(RFQ).where(RFQ.reference_id == payload.reference_id)).scalar_one_or_none()
    if existing_ref:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REFERENCE_ID_CONFLICT",
                "message": f"RFQ with reference_id '{payload.reference_id}' already exists.",
                "details": {"reference_id": payload.reference_id},
            },
        )

    # 2. Check all invited suppliers exist
    unique_supplier_ids = list(set(payload.invited_supplier_ids))
    suppliers = db.execute(select(Supplier).where(Supplier.id.in_(unique_supplier_ids))).scalars().all()
    if len(suppliers) != len(unique_supplier_ids):
        found_ids = {s.id for s in suppliers}
        missing_ids = [str(sid) for sid in unique_supplier_ids if sid not in found_ids]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SUPPLIER_NOT_FOUND",
                "message": f"One or more invited suppliers were not found: {', '.join(missing_ids)}",
                "details": {"missing_ids": missing_ids},
            },
        )

    # 3. Derive initial status
    initial_status = derive_status(
        bid_start_time=payload.bid_start_time,
        current_close_time=payload.bid_close_time,
        forced_close_time=payload.forced_close_time,
        now=now,
    )

    # 4. Insert RFQ
    rfq = RFQ(
        reference_id=payload.reference_id,
        name=payload.name,
        currency=payload.currency,
        pickup_date=payload.pickup_date,
        auction_type=payload.auction_type,
        bid_start_time=payload.bid_start_time,
        original_close_time=payload.bid_close_time,
        current_close_time=payload.bid_close_time,
        forced_close_time=payload.forced_close_time,
        status=initial_status,
        created_at=now,
    )
    db.add(rfq)
    db.flush()

    # 5. Insert British config if applicable
    if payload.auction_type == AuctionType.BRITISH and payload.british_config:
        config = BritishAuctionConfig(
            rfq_id=rfq.id,
            trigger_window_minutes=payload.british_config.trigger_window_minutes,
            extension_minutes=payload.british_config.extension_minutes,
            extension_trigger=payload.british_config.extension_trigger,
        )
        db.add(config)

    # 6. Insert supplier invitations
    for s_id in unique_supplier_ids:
        invitation = RFQSupplier(
            rfq_id=rfq.id,
            supplier_id=s_id,
            invited_at=now,
        )
        db.add(invitation)

    # 7. Write AUCTION_CREATED event
    created_event = AuctionEvent(
        rfq_id=rfq.id,
        event_type=AuctionEventType.AUCTION_CREATED,
        bid_id=None,
        payload={
            "rfq_id": str(rfq.id),
            "name": rfq.name,
            "reference_id": rfq.reference_id,
            "auction_type": rfq.auction_type.value,
        },
        reason=f"Auction '{rfq.name}' was created ({rfq.auction_type.value}).",
        occurred_at=now,
        created_at=now,
        is_recovered=False,
    )
    db.add(created_event)

    db.commit()
    db.refresh(rfq)

    # Return full detail
    return get_rfq_detail_response(rfq.id, db, clock)


@router.get("/rfqs", response_model=RFQListResponse, tags=["RFQs"])
def list_rfqs(
    status: Optional[AuctionStatus] = Query(None, description="Filter by derived auction status"),
    q: Optional[str] = Query(None, description="Search by name or reference_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    now = clock.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # SQL CASE expression for timestamp-derived status (authoritative, never reads cached column)
    # Dialect-safe: compare UTC timestamps
    status_case = case(
        (literal(now) < RFQ.bid_start_time, literal(AuctionStatus.SCHEDULED.value)),
        (literal(now) < RFQ.current_close_time, literal(AuctionStatus.ACTIVE.value)),
        (RFQ.current_close_time == RFQ.forced_close_time, literal(AuctionStatus.FORCE_CLOSED.value)),
        else_=literal(AuctionStatus.CLOSED.value),
    )

    query = select(RFQ)

    # Filter by q
    if q:
        query = query.where(
            or_(
                RFQ.name.ilike(f"%{q.strip()}%"),
                RFQ.reference_id.ilike(f"%{q.strip()}%"),
            )
        )

    # Filter by derived status
    if status:
        query = query.where(status_case == status.value)

    # Count total
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    # Order by close time ASC (soonest closing first)
    items = db.execute(
        query.order_by(RFQ.current_close_time.asc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    # Compute lowest bid per RFQ
    rfq_items: list[RFQListItem] = []
    for r in items:
        # Lowest bid
        lowest_bid_val = db.scalar(
            select(func.min(Bid.total_price)).where(Bid.rfq_id == r.id)
        )
        derived = derive_status(r.bid_start_time, r.current_close_time, r.forced_close_time, now)

        rfq_items.append(
            RFQListItem(
                id=r.id,
                reference_id=r.reference_id,
                name=r.name,
                currency=r.currency,
                auction_type=r.auction_type,
                current_lowest_bid=lowest_bid_val,
                bid_start_time=r.bid_start_time,
                original_close_time=r.original_close_time,
                current_close_time=r.current_close_time,
                forced_close_time=r.forced_close_time,
                status=derived,
            )
        )

    return RFQListResponse(
        items=rfq_items,
        total=total,
        page=page,
        page_size=page_size,
        server_time=now,
    )


@router.get("/rfqs/{id}", response_model=RFQDetailResponse, tags=["RFQs"])
def get_rfq(
    id: UUID,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    return get_rfq_detail_response(id, db, clock)


def get_rfq_detail_response(rfq_id: UUID, db: Session, clock: Clock) -> RFQDetailResponse:
    now = clock.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    rfq = db.execute(select(RFQ).where(RFQ.id == rfq_id)).scalar_one_or_none()
    if not rfq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": f"RFQ {rfq_id} was not found.", "details": {"rfq_id": str(rfq_id)}},
        )

    derived = derive_status(rfq.bid_start_time, rfq.current_close_time, rfq.forced_close_time, now)

    # Config
    b_config = None
    if rfq.auction_type == AuctionType.BRITISH and rfq.british_config:
        b_config = BritishConfigSchema.model_validate(rfq.british_config)

    # Invited suppliers
    invitations = db.execute(
        select(Supplier)
        .join(RFQSupplier, RFQSupplier.supplier_id == Supplier.id)
        .where(RFQSupplier.rfq_id == rfq_id)
        .order_by(Supplier.name.asc())
    ).scalars().all()
    invited_suppliers = [SupplierResponse.model_validate(s) for s in invitations]

    # Bids & Ranking
    all_bids = db.execute(select(Bid).where(Bid.rfq_id == rfq_id)).scalars().all()
    engine_ranking = compute_ranking(all_bids)

    # Build full supplier ranking view including unbid suppliers
    ranking_by_supplier_id = {str(r.supplier_id): r for r in engine_ranking}

    ranking_list: list[SupplierRankDetail] = []
    # 1. Add ranked suppliers first (L1, L2, ...)
    for r in engine_ranking:
        s_obj = next((s for s in invitations if str(s.id) == str(r.supplier_id)), None)
        supplier_name = s_obj.name if s_obj else r.carrier_name
        ranking_list.append(
            SupplierRankDetail(
                rank=r.rank,
                supplier_id=r.best_bid.supplier_id if isinstance(r.best_bid.supplier_id, UUID) else UUID(str(r.best_bid.supplier_id)),
                supplier_name=supplier_name,
                carrier_name=r.carrier_name,
                freight_charges=r.best_bid.freight_charges,
                origin_charges=r.best_bid.origin_charges,
                destination_charges=r.best_bid.destination_charges,
                total_price=r.best_bid.total_price,
                transit_time_days=r.best_bid.transit_time_days,
                quote_validity_days=r.best_bid.quote_validity_days,
                submitted_at=r.best_bid.submitted_at,
                bid_id=r.best_bid.id if isinstance(r.best_bid.id, UUID) else UUID(str(r.best_bid.id)),
                no_bid=False,
            )
        )

    # 2. Add invited suppliers who haven't placed a bid
    for s in invitations:
        if str(s.id) not in ranking_by_supplier_id:
            ranking_list.append(
                SupplierRankDetail(
                    rank=None,
                    supplier_id=s.id,
                    supplier_name=s.name,
                    carrier_name=None,
                    total_price=None,
                    no_bid=True,
                )
            )

    # Stats Strip
    extension_count = db.scalar(
        select(func.count()).select_from(AuctionEvent).where(
            AuctionEvent.rfq_id == rfq_id,
            AuctionEvent.event_type == AuctionEventType.TIME_EXTENDED,
        )
    ) or 0

    first_bid = None
    if all_bids:
        first_bid = db.scalar(
            select(Bid.total_price)
            .where(Bid.rfq_id == rfq_id)
            .order_by(Bid.submitted_at.asc(), Bid.id.asc())
            .limit(1)
        )

    current_lowest = engine_ranking[0].best_bid.total_price if engine_ranking else None

    price_improvement_pct = None
    if first_bid and current_lowest and first_bid > 0:
        improvement = ((first_bid - current_lowest) / first_bid) * Decimal("100")
        price_improvement_pct = max(Decimal("0.00"), improvement)

    stats = RFQStats(
        total_bids=len(all_bids),
        suppliers_bidding=len(engine_ranking),
        suppliers_invited=len(invited_suppliers),
        extension_count=extension_count,
        first_bid_price=first_bid,
        current_lowest_price=current_lowest,
        price_improvement_pct=price_improvement_pct,
    )

    return RFQDetailResponse(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        currency=rfq.currency,
        pickup_date=rfq.pickup_date,
        auction_type=rfq.auction_type,
        bid_start_time=rfq.bid_start_time,
        original_close_time=rfq.original_close_time,
        current_close_time=rfq.current_close_time,
        forced_close_time=rfq.forced_close_time,
        status=derived,
        british_config=b_config,
        invited_suppliers=invited_suppliers,
        ranking=ranking_list,
        stats=stats,
        created_at=rfq.created_at,
        server_time=now,
    )


@router.get("/rfqs/{id}/bids", response_model=BidHistoryListResponse, tags=["RFQs"])
def list_bids_history(
    id: UUID,
    sort: str = Query("price", pattern="^(price|time)$", description="Sort by price (ASC) or time (DESC)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    now = clock.now()
    rfq = db.execute(select(RFQ).where(RFQ.id == id)).scalar_one_or_none()
    if not rfq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": f"RFQ {id} was not found.", "details": {"rfq_id": str(id)}},
        )

    query = select(Bid).where(Bid.rfq_id == id)
    if sort == "price":
        query = query.order_by(Bid.total_price.asc(), Bid.submitted_at.asc())
    else:  # time
        query = query.order_by(Bid.submitted_at.desc(), Bid.id.desc())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    return BidHistoryListResponse(
        items=[BidRecord.model_validate(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
        server_time=now,
    )


@router.post("/rfqs/{id}/bids", response_model=BidSubmissionResult, tags=["RFQs"])
def post_bid(
    id: UUID,
    payload: BidCreate,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    try:
        result, is_replay = submit_bid(
            rfq_id=id,
            bid_in=payload,
            session=db,
            clock=clock,
            idempotency_key=idempotency_key,
        )
    except RFQNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": str(e), "details": {"rfq_id": str(e.rfq_id)}},
        )
    except SupplierNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SUPPLIER_NOT_FOUND", "message": str(e), "details": {"supplier_id": str(e.supplier_id)}},
        )
    except SupplierNotInvitedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SUPPLIER_NOT_INVITED", "message": str(e), "details": {"rfq_id": str(e.rfq_id), "supplier_id": str(e.supplier_id)}},
        )
    except AuctionNotStartedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AUCTION_NOT_STARTED", "message": str(e), "details": {"start_time": e.start_time.isoformat()}},
        )
    except AuctionClosedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AUCTION_CLOSED", "message": str(e), "details": {"close_time": e.close_time.isoformat(), "forced": e.forced}},
        )
    except BidNotLowerError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "BID_NOT_LOWER",
                "message": str(e),
                "details": {
                    "previous_best": str(e.previous_best),
                    "attempted_bid": str(e.attempted_bid),
                },
            },
        )
    except IdempotencyKeyConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IDEMPOTENCY_KEY_CONFLICT",
                "message": str(e),
                "details": {"idempotency_key": e.idempotency_key},
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": str(e), "details": {}},
        )

    if is_replay:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replay"] = "true"
    else:
        response.status_code = status.HTTP_201_CREATED

    return result


@router.get("/rfqs/{id}/activity", response_model=AuctionEventListResponse, tags=["RFQs"])
def list_activity_log(
    id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    now = clock.now()
    rfq = db.execute(select(RFQ).where(RFQ.id == id)).scalar_one_or_none()
    if not rfq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": f"RFQ {id} was not found.", "details": {"rfq_id": str(id)}},
        )

    # Activity log is ordered chronologically by (occurred_at DESC, id DESC) for UI display (newest first)
    query = select(AuctionEvent).where(AuctionEvent.rfq_id == id).order_by(AuctionEvent.occurred_at.desc(), AuctionEvent.id.desc())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    return AuctionEventListResponse(
        items=[AuctionEventItem.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        server_time=now,
    )
