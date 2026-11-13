from datetime import datetime, timezone


def test_scripted_acceptance_scenario(client, fake_clock):
    """
    Scripted acceptance scenario from Section 8:
    - Original Close: 6:00 PM (18:00)
    - Forced Close: 6:30 PM (18:30)
    - Trigger window X: 10 minutes
    - Extension duration Y: 5 minutes
    - Trigger: L1_CHANGE_IN_LAST_X

    Step 1: 5:45 PM -> A bids 1000 (outside window, close stays 6:00 PM)
    Step 2: 5:55 PM -> B bids 950 (L1 change, close extends 6:00 -> 6:05 PM)
    Step 3: 6:03 PM -> B bids 940 (B stays L1, no extension, close stays 6:05 PM)
    Step 4: 6:04 PM -> A bids 900 (L1 change, close extends 6:05 -> 6:10 PM)
    Step 5..N: Continue until cap proves close never passes 6:30 PM
    Final: Verify FORCE_CLOSED and that later bids are rejected.
    """
    # 1. Setup Suppliers
    res_a = client.post("/api/v1/suppliers", json={"name": "Carrier Alpha"})
    assert res_a.status_code == 201
    s_a = res_a.json()

    res_b = client.post("/api/v1/suppliers", json={"name": "Carrier Beta"})
    assert res_b.status_code == 201
    s_b = res_b.json()

    t_start = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)

    # Create RFQ
    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Acceptance British Auction",
            "reference_id": "RFQ-ACCEPT-01",
            "currency": "INR",
            "auction_type": "BRITISH",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s_a["id"], s_b["id"]],
            "british_config": {
                "trigger_window_minutes": 10,
                "extension_minutes": 5,
                "extension_trigger": "L1_CHANGE_IN_LAST_X",
            },
        },
    )
    assert res_rfq.status_code == 201
    rfq_id = res_rfq.json()["id"]

    # --- Step 1: 5:45 PM (17:45) -> A bids 1000 (outside window [17:50, 18:00)) ---
    fake_clock.set_time(datetime(2026, 11, 20, 17, 45, 0, tzinfo=timezone.utc))
    r1 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "supplier_id": s_a["id"],
            "freight_charges": "1000.00",
            "origin_charges": "0.00",
            "destination_charges": "0.00",
            "transit_time_days": 5,
            "quote_validity_days": 10,
        },
    )
    assert r1.status_code == 201
    d1 = r1.json()
    assert d1["rank"] == 1
    assert d1["extended"] is False
    assert d1["new_close_time"] == "2026-11-20T18:00:00Z"

    # --- Step 2: 5:55 PM (17:55) -> B bids 950 (inside window, L1 changes A -> B) ---
    fake_clock.set_time(datetime(2026, 11, 20, 17, 55, 0, tzinfo=timezone.utc))
    r2 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "supplier_id": s_b["id"],
            "freight_charges": "950.00",
            "origin_charges": "0.00",
            "destination_charges": "0.00",
            "transit_time_days": 5,
            "quote_validity_days": 10,
        },
    )
    assert r2.status_code == 201
    d2 = r2.json()
    assert d2["rank"] == 1
    assert d2["extended"] is True
    # Close extended by 5 min: 18:00 -> 18:05
    assert d2["new_close_time"] == "2026-11-20T18:05:00Z"

    # --- Step 3: 6:03 PM (18:03) -> B bids 940 (inside new window [17:55, 18:05)) ---
    # B improves own price, B stays L1 -> NO extension!
    fake_clock.set_time(datetime(2026, 11, 20, 18, 3, 0, tzinfo=timezone.utc))
    r3 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "supplier_id": s_b["id"],
            "freight_charges": "940.00",
            "origin_charges": "0.00",
            "destination_charges": "0.00",
            "transit_time_days": 5,
            "quote_validity_days": 10,
        },
    )
    assert r3.status_code == 201
    d3 = r3.json()
    assert d3["rank"] == 1
    assert d3["extended"] is False
    assert d3["new_close_time"] == "2026-11-20T18:05:00Z"

    # --- Step 4: 6:04 PM (18:04) -> A bids 900 (inside window, L1 changes B -> A) ---
    fake_clock.set_time(datetime(2026, 11, 20, 18, 4, 0, tzinfo=timezone.utc))
    r4 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "supplier_id": s_a["id"],
            "freight_charges": "900.00",
            "origin_charges": "0.00",
            "destination_charges": "0.00",
            "transit_time_days": 5,
            "quote_validity_days": 10,
        },
    )
    assert r4.status_code == 201
    d4 = r4.json()
    assert d4["rank"] == 1
    assert d4["extended"] is True
    # Close extended: 18:05 -> 18:10
    assert d4["new_close_time"] == "2026-11-20T18:10:00Z"

    # --- Step 5..N: Continue chained extensions up to the 18:30:00 cap ---
    # 6:09 PM -> B bids 850 (L1 change, close -> 18:15)
    fake_clock.set_time(datetime(2026, 11, 20, 18, 9, 0, tzinfo=timezone.utc))
    r5 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={"supplier_id": s_b["id"], "freight_charges": "850.00", "origin_charges": "0.00", "destination_charges": "0.00", "transit_time_days": 5, "quote_validity_days": 10},
    )
    assert r5.json()["new_close_time"] == "2026-11-20T18:15:00Z"

    # 6:14 PM -> A bids 800 (L1 change, close -> 18:20)
    fake_clock.set_time(datetime(2026, 11, 20, 18, 14, 0, tzinfo=timezone.utc))
    r6 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={"supplier_id": s_a["id"], "freight_charges": "800.00", "origin_charges": "0.00", "destination_charges": "0.00", "transit_time_days": 5, "quote_validity_days": 10},
    )
    assert r6.json()["new_close_time"] == "2026-11-20T18:20:00Z"

    # 6:19 PM -> B bids 750 (L1 change, close -> 18:25)
    fake_clock.set_time(datetime(2026, 11, 20, 18, 19, 0, tzinfo=timezone.utc))
    r7 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={"supplier_id": s_b["id"], "freight_charges": "750.00", "origin_charges": "0.00", "destination_charges": "0.00", "transit_time_days": 5, "quote_validity_days": 10},
    )
    assert r7.json()["new_close_time"] == "2026-11-20T18:25:00Z"

    # 6:24 PM -> A bids 700 (L1 change, close -> 18:30 CAPPED at forced_close!)
    fake_clock.set_time(datetime(2026, 11, 20, 18, 24, 0, tzinfo=timezone.utc))
    r8 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={"supplier_id": s_a["id"], "freight_charges": "700.00", "origin_charges": "0.00", "destination_charges": "0.00", "transit_time_days": 5, "quote_validity_days": 10},
    )
    assert r8.json()["new_close_time"] == "2026-11-20T18:30:00Z"
    assert r8.json()["extended"] is True

    # 6:28 PM -> B bids 650 (inside window [18:20, 18:30), L1 changes, but ALREADY AT CAP 18:30)
    # Must NOT extend beyond 18:30:00! Writes EXTENSION_SKIPPED_AT_FORCED_CLOSE event
    fake_clock.set_time(datetime(2026, 11, 20, 18, 28, 0, tzinfo=timezone.utc))
    r9 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={"supplier_id": s_b["id"], "freight_charges": "650.00", "origin_charges": "0.00", "destination_charges": "0.00", "transit_time_days": 5, "quote_validity_days": 10},
    )
    assert r9.status_code == 201
    d9 = r9.json()
    assert d9["rank"] == 1
    assert d9["extended"] is False  # Extension skipped!
    assert d9["new_close_time"] == "2026-11-20T18:30:00Z"

    # Verify EXTENSION_SKIPPED_AT_FORCED_CLOSE event exists in activity log
    activity = client.get(f"/api/v1/rfqs/{rfq_id}/activity").json()
    event_types = [e["event_type"] for e in activity["items"]]
    assert "EXTENSION_SKIPPED_AT_FORCED_CLOSE" in event_types

    # --- Advance clock past 6:30 PM (e.g. 6:31 PM) ---
    fake_clock.set_time(datetime(2026, 11, 20, 18, 31, 0, tzinfo=timezone.utc))

    # Verify RFQ status is FORCE_CLOSED
    rfq_final = client.get(f"/api/v1/rfqs/{rfq_id}").json()
    assert rfq_final["status"] == "FORCE_CLOSED"

    # Verify any further bid is rejected
    r_late = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={"supplier_id": s_a["id"], "freight_charges": "600.00", "origin_charges": "0.00", "destination_charges": "0.00", "transit_time_days": 5, "quote_validity_days": 10},
    )
    assert r_late.status_code == 409
    assert r_late.json()["error"]["code"] == "AUCTION_CLOSED"

