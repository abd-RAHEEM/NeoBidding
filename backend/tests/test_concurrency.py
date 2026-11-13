from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest


def test_concurrent_bids_in_trigger_window(client, fake_clock):
    # Create 5 suppliers
    suppliers = []
    for i in range(5):
        res = client.post("/api/v1/suppliers", json={"name": f"Concurrent Carrier {i}"})
        suppliers.append(res.json())

    t_start = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 15, tzinfo=timezone.utc)  # 15 min forced close

    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "High Concurrency Auction",
            "reference_id": "RFQ-CONCUR-01",
            "currency": "INR",
            "auction_type": "BRITISH",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s["id"] for s in suppliers],
            "british_config": {
                "trigger_window_minutes": 10,
                "extension_minutes": 5,
                "extension_trigger": "BID_IN_LAST_X",
            },
        },
    )
    rfq_id = res_rfq.json()["id"]

    # Set clock inside window: 17:55:00
    fake_clock.set_time(datetime(2026, 11, 20, 17, 55, 0, tzinfo=timezone.utc))

    # Prepare 25 distinct bids from different suppliers with decreasing prices
    tasks = []
    base_price = 10000
    for i in range(25):
        s = suppliers[i % len(suppliers)]
        price = str(base_price - (i * 100))
        tasks.append((s["id"], price))

    def place_bid(task_info):
        supplier_id, price = task_info
        return client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": supplier_id,
                "freight_charges": price,
                "origin_charges": "0.00",
                "destination_charges": "0.00",
                "transit_time_days": 5,
                "quote_validity_days": 10,
            },
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(place_bid, tasks))

    # Check outcomes
    status_codes = [r.status_code for r in responses]
    # In SQLite threaded mode, either 201 (success) or 422 (if a supplier's thread raced with its own bid)
    assert any(c == 201 for c in status_codes)

    # Check final RFQ state: current_close_time must NEVER exceed forced_close_time!
    rfq_final = client.get(f"/api/v1/rfqs/{rfq_id}").json()
    assert rfq_final["current_close_time"] <= rfq_final["forced_close_time"]
    # 18:00 -> 18:05 -> 18:10 (at 18:10, window is [18:00, 18:10), so bids at 17:55 are outside window)
    assert rfq_final["current_close_time"] == "2026-11-20T18:10:00Z"

    # Check activity log consistency
    activity = client.get(f"/api/v1/rfqs/{rfq_id}/activity").json()
    assert activity["total"] > 0
