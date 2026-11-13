from datetime import datetime, timedelta, timezone
import uuid


def test_idempotency_workflow(client, fake_clock):
    # Setup supplier & RFQ
    res_s = client.post("/api/v1/suppliers", json={"name": "Evergreen"})
    supplier = res_s.json()

    t_start = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    t_forced = datetime(2026, 11, 20, 18, 30, tzinfo=timezone.utc)

    res_rfq = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Idempotency Test Auction",
            "reference_id": "RFQ-IDEM-01",
            "currency": "USD",
            "auction_type": "STANDARD",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [supplier["id"]],
        },
    )
    rfq = res_rfq.json()
    rfq_id = rfq["id"]

    fake_clock.set_time(t_start + timedelta(hours=1))

    idem_key = str(uuid.uuid4())
    payload = {
        "supplier_id": supplier["id"],
        "freight_charges": "3000.00",
        "origin_charges": "500.00",
        "destination_charges": "500.00",
        "transit_time_days": 15,
        "quote_validity_days": 30,
    }

    # 1. First submission with idempotency key -> 201 Created
    res1 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json=payload,
        headers={"Idempotency-Key": idem_key},
    )
    assert res1.status_code == 201
    assert "Idempotent-Replay" not in res1.headers
    data1 = res1.json()

    # 2. Replay with exact same key and payload -> 200 OK + header Idempotent-Replay: true
    res2 = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json=payload,
        headers={"Idempotency-Key": idem_key},
    )
    assert res2.status_code == 200
    assert res2.headers.get("Idempotent-Replay") == "true"
    data2 = res2.json()
    assert data1["bid"]["id"] == data2["bid"]["id"]

    # Verify no second bid was inserted in database
    history = client.get(f"/api/v1/rfqs/{rfq_id}/bids").json()
    assert history["total"] == 1

    # 3. Same key with DIFFERENT payload -> 409 IDEMPOTENCY_KEY_CONFLICT
    different_payload = dict(payload)
    different_payload["freight_charges"] = "2800.00"
    res_conflict = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json=different_payload,
        headers={"Idempotency-Key": idem_key},
    )
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    # 4. Advance clock past auction close (19:00:00)
    fake_clock.set_time(t_close + timedelta(hours=1))

    # A new bid is rejected because auction is closed
    res_new_closed = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "supplier_id": supplier["id"],
            "freight_charges": "2500.00",
            "origin_charges": "500.00",
            "destination_charges": "500.00",
            "transit_time_days": 15,
            "quote_validity_days": 30,
        },
    )
    assert res_new_closed.status_code == 409
    assert res_new_closed.json()["error"]["code"] == "AUCTION_CLOSED"

    # But replay of the ORIGINAL idempotent submission still succeeds!
    res_replay_closed = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json=payload,
        headers={"Idempotency-Key": idem_key},
    )
    assert res_replay_closed.status_code == 200
    assert res_replay_closed.headers.get("Idempotent-Replay") == "true"
    assert res_replay_closed.json()["bid"]["id"] == data1["bid"]["id"]

    # 5. Requests without an idempotency key still work normally
    fake_clock.set_time(t_start + timedelta(minutes=30))
    # Create another active RFQ to test key-less bids
    res_rfq2 = client.post(
        "/api/v1/rfqs",
        json={
            "name": "Keyless Test",
            "reference_id": "RFQ-KEYLESS",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [supplier["id"]],
        },
    )
    rfq2_id = res_rfq2.json()["id"]

    res_no_key = client.post(
        f"/api/v1/rfqs/{rfq2_id}/bids",
        json=payload,
    )
    assert res_no_key.status_code == 201
    assert "Idempotent-Replay" not in res_no_key.headers

