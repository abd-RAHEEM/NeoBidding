from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
from uuid import UUID
import pytest
from sqlalchemy import select

from app.models.entities import AuctionEvent, RFQ
from app.models.enums import AuctionEventType, AuctionStatus
from app.services.tasks import run_sweeper


def test_api_derived_status_correct_before_sweeper_runs(client, fake_clock):
    # Setup supplier & RFQ
    res_s = client.post("/api/v1/suppliers", json={"name": "Lifecycle Carrier"})
    s = res_s.json()

    t_start = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 30, tzinfo=timezone.utc)

    # Created at 09:50 -> SCHEDULED
    fake_clock.set_time(t_start - timedelta(minutes=10))
    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Sweeper Recovery Test",
            "reference_id": "RFQ-SWEEP-01",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s["id"]],
        },
    )
    rfq_id = res_rfq.json()["id"]

    # 1. Advance clock past close time (18:10) WITHOUT running sweeper
    fake_clock.set_time(t_close + timedelta(minutes=10))

    # The API should ALREADY report CLOSED because status is derived on read!
    rfq_api = client.get(f"/api/v1/rfqs/{rfq_id}").json()
    assert rfq_api["status"] == "CLOSED"

    # List endpoint should also filter and report CLOSED correctly!
    list_res = client.get("/api/v1/rfqs?status=CLOSED").json()
    assert any(item["id"] == rfq_id for item in list_res["items"])


def test_sweeper_recovers_missing_auction_closed_event(test_db, client, fake_clock):
    res_s = client.post("/api/v1/suppliers", json={"name": "Sweeper Carrier 2"})
    s = res_s.json()

    t_start = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 30, tzinfo=timezone.utc)

    fake_clock.set_time(t_start + timedelta(hours=1))  # ACTIVE
    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Audit Recovery Test",
            "reference_id": "RFQ-SWEEP-02",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s["id"]],
        },
    )
    rfq_id = UUID(res_rfq.json()["id"])

    # Advance clock past close (18:15)
    now = t_close + timedelta(minutes=15)
    fake_clock.set_time(now)

    # Run the sweeper once
    processed = run_sweeper(db_session=test_db, current_time=now)
    assert processed >= 1

    # Assert AUCTION_CLOSED event exists with occurred_at == close_time and is_recovered == True
    events = test_db.execute(
        select(AuctionEvent).where(
            AuctionEvent.rfq_id == rfq_id,
            AuctionEvent.event_type == AuctionEventType.AUCTION_CLOSED,
        )
    ).scalars().all()
    assert len(events) == 1
    closed_event = events[0]
    # In SQLite string/tz comparisons:
    assert closed_event.occurred_at.strftime("%Y-%m-%d %H:%M:%S") == t_close.strftime("%Y-%m-%d %H:%M:%S")
    assert closed_event.is_recovered is True

    # Assert cached status in DB was updated to CLOSED
    rfq_db = test_db.execute(select(RFQ).where(RFQ.id == rfq_id)).scalar_one()
    assert rfq_db.status == AuctionStatus.CLOSED


def test_multi_transition_recovery_during_celery_outage(test_db, client, fake_clock):
    """
    Spec case: auction start 5 PM (17:00), close 6 PM (18:00), sweeper first runs at 6:10 PM (18:10).
    Assert BOTH AUCTION_STARTED (5:00 PM) and AUCTION_CLOSED (6:00 PM) exist, in chronological order.
    """
    res_s = client.post("/api/v1/suppliers", json={"name": "Outage Carrier"})
    s = res_s.json()

    t_start = datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 30, tzinfo=timezone.utc)

    # RFQ created before start (16:50)
    fake_clock.set_time(datetime(2026, 11, 20, 16, 50, tzinfo=timezone.utc))
    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Outage Catchup RFQ",
            "reference_id": "RFQ-OUTAGE-01",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s["id"]],
        },
    )
    rfq_id = UUID(res_rfq.json()["id"])

    # Celery is offline from 4:55 PM to 6:10 PM. Advance clock to 6:10 PM:
    now = datetime(2026, 11, 20, 18, 10, tzinfo=timezone.utc)
    fake_clock.set_time(now)

    # Sweeper runs for the first time at 6:10 PM
    run_sweeper(db_session=test_db, current_time=now)

    # Fetch all events ordered by occurred_at ASC
    all_events = test_db.execute(
        select(AuctionEvent)
        .where(AuctionEvent.rfq_id == rfq_id)
        .order_by(AuctionEvent.occurred_at.asc(), AuctionEvent.id.asc())
    ).scalars().all()

    event_types = [e.event_type for e in all_events]
    # Must have AUCTION_CREATED, AUCTION_STARTED, AUCTION_CLOSED in order
    assert AuctionEventType.AUCTION_STARTED in event_types
    assert AuctionEventType.AUCTION_CLOSED in event_types

    started_event = next(e for e in all_events if e.event_type == AuctionEventType.AUCTION_STARTED)
    closed_event = next(e for e in all_events if e.event_type == AuctionEventType.AUCTION_CLOSED)

    # Chronological order verified
    assert started_event.occurred_at < closed_event.occurred_at
    assert started_event.occurred_at.strftime("%H:%M") == "17:00"
    assert closed_event.occurred_at.strftime("%H:%M") == "18:00"
    assert started_event.is_recovered is True
    assert closed_event.is_recovered is True

    # Running sweeper a second time creates NO duplicates (idempotent)
    run_sweeper(db_session=test_db, current_time=now)
    events_after = test_db.execute(
        select(AuctionEvent).where(AuctionEvent.rfq_id == rfq_id)
    ).scalars().all()
    assert len(events_after) == len(all_events)


def test_force_closed_recovery(test_db, client, fake_clock):
    res_s = client.post("/api/v1/suppliers", json={"name": "Force Carrier"})
    s = res_s.json()

    t_start = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 5, tzinfo=timezone.utc)  # Forced is 18:05

    fake_clock.set_time(t_start + timedelta(hours=1))
    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Force Close Recovery",
            "reference_id": "RFQ-FORCE-RECOVER",
            "currency": "INR",
            "auction_type": "BRITISH",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s["id"]],
            "british_config": {
                "trigger_window_minutes": 10,
                "extension_minutes": 5,
                "extension_trigger": "BID_IN_LAST_X",
            },
        },
    )
    rfq_id = UUID(res_rfq.json()["id"])

    # In trigger window (17:55), submit bid which extends close to 18:05 (cap!)
    fake_clock.set_time(datetime(2026, 11, 20, 17, 55, 0, tzinfo=timezone.utc))
    res_bid = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "supplier_id": s["id"],
            "freight_charges": "1000.00",
            "origin_charges": "0.00",
            "destination_charges": "0.00",
            "transit_time_days": 5,
            "quote_validity_days": 10,
        },
    )
    assert res_bid.status_code == 201
    assert res_bid.json()["new_close_time"] == "2026-11-20T18:05:00Z"

    # Advance past forced close (18:10)
    now = datetime(2026, 11, 20, 18, 10, tzinfo=timezone.utc)
    fake_clock.set_time(now)

    run_sweeper(db_session=test_db, current_time=now)

    events = test_db.execute(
        select(AuctionEvent).where(
            AuctionEvent.rfq_id == rfq_id,
            AuctionEvent.event_type == AuctionEventType.AUCTION_FORCE_CLOSED,
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].is_recovered is True

