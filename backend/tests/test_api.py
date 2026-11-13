from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from app.models.enums import AuctionStatus, AuctionType, ExtensionTrigger


def create_sample_suppliers(client):
    res_a = client.post("/api/v1/suppliers", json={"name": "Maersk"})
    assert res_a.status_code == 201
    s_a = res_a.json()

    res_b = client.post("/api/v1/suppliers", json={"name": "DHL"})
    assert res_b.status_code == 201
    s_b = res_b.json()

    res_c = client.post("/api/v1/suppliers", json={"name": "FedEx"})
    assert res_c.status_code == 201
    s_c = res_c.json()

    return s_a, s_b, s_c


def test_health_endpoint(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert "time" in data


def test_supplier_creation_and_listing(client):
    res = client.post("/api/v1/suppliers", json={"name": "Kuehne+Nagel"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Kuehne+Nagel"
    assert "id" in data

    # Conflict on duplicate name
    res_dup = client.post("/api/v1/suppliers", json={"name": "Kuehne+Nagel"})
    assert res_dup.status_code == 409
    assert res_dup.json()["error"]["code"] == "SUPPLIER_NAME_CONFLICT"

    # List with search
    res_list = client.get("/api/v1/suppliers?q=Kuehne")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1
    assert res_list.json()["items"][0]["name"] == "Kuehne+Nagel"


class TestRFQValidation:
    def test_rfq_time_validations(self, client):
        s_a, _, _ = create_sample_suppliers(client)
        t_start = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc).isoformat()
        t_close = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc).isoformat()
        t_forced = datetime(2026, 11, 20, 18, 30, tzinfo=timezone.utc).isoformat()

        # 1. Close <= Start
        res = client.post(
            "/api/v1/rfqs",
            json={
                "name": "Invalid Times",
                "reference_id": "RFQ-ERR-1",
                "bid_start_time": t_close,
                "bid_close_time": t_start,
                "forced_close_time": t_forced,
                "invited_supplier_ids": [s_a["id"]],
            },
        )
        assert res.status_code == 422

        # 2. Forced <= Close
        res = client.post(
            "/api/v1/rfqs",
            json={
                "name": "Invalid Times 2",
                "reference_id": "RFQ-ERR-2",
                "bid_start_time": t_start,
                "bid_close_time": t_forced,
                "forced_close_time": t_close,
                "invited_supplier_ids": [s_a["id"]],
            },
        )
        assert res.status_code == 422

        # 3. No invited suppliers
        res = client.post(
            "/api/v1/rfqs",
            json={
                "name": "No Suppliers",
                "reference_id": "RFQ-ERR-3",
                "bid_start_time": t_start,
                "bid_close_time": t_close,
                "forced_close_time": t_forced,
                "invited_supplier_ids": [],
            },
        )
        assert res.status_code == 422

        # 4. British auction requires british_config
        res = client.post(
            "/api/v1/rfqs",
            json={
                "name": "Missing Config",
                "reference_id": "RFQ-ERR-4",
                "auction_type": "BRITISH",
                "bid_start_time": t_start,
                "bid_close_time": t_close,
                "forced_close_time": t_forced,
                "invited_supplier_ids": [s_a["id"]],
            },
        )
        assert res.status_code == 422

        # 5. Non-existent invited supplier
        res = client.post(
            "/api/v1/rfqs",
            json={
                "name": "Bad Supplier",
                "reference_id": "RFQ-ERR-5",
                "bid_start_time": t_start,
                "bid_close_time": t_close,
                "forced_close_time": t_forced,
                "invited_supplier_ids": [str(uuid.uuid4())],
            },
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "SUPPLIER_NOT_FOUND"


class TestBiddingWorkflow:
    def test_complete_auction_flow_and_validation(self, client, fake_clock):
        s_a, s_b, s_c = create_sample_suppliers(client)

        t_start = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        t_close = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
        t_forced = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)

        # Create British RFQ
        rfq_payload = {
            "name": "Asia-Europe Trade",
            "reference_id": "RFQ-AET-01",
            "currency": "INR",
            "auction_type": "BRITISH",
            "bid_start_time": t_start.isoformat(),
            "bid_close_time": t_close.isoformat(),
            "forced_close_time": t_forced.isoformat(),
            "invited_supplier_ids": [s_a["id"], s_b["id"]],  # s_c is NOT invited
            "british_config": {
                "trigger_window_minutes": 10,
                "extension_minutes": 5,
                "extension_trigger": "L1_CHANGE_IN_LAST_X",
            },
        }

        # Clock is at 10:00:00
        fake_clock.set_time(t_start - timedelta(minutes=5))
        res_create = client.post("/api/v1/rfqs", json=rfq_payload)
        assert res_create.status_code == 201
        rfq = res_create.json()
        rfq_id = rfq["id"]
        assert rfq["status"] == "SCHEDULED"

        # 1. Bid before start is rejected
        res_early = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_a["id"],
                "freight_charges": "50000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_early.status_code == 409
        assert res_early.json()["error"]["code"] == "AUCTION_NOT_STARTED"

        # Advance clock to active period: 10:05:00
        fake_clock.set_time(t_start + timedelta(minutes=5))

        # 2. Uninvited supplier rejected
        res_uninvited = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_c["id"],
                "freight_charges": "40000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_uninvited.status_code == 403
        assert res_uninvited.json()["error"]["code"] == "SUPPLIER_NOT_INVITED"

        # 3. Valid first bid outside window (10:05:00)
        res_bid1 = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_a["id"],
                "freight_charges": "40000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_bid1.status_code == 201
        data_bid1 = res_bid1.json()
        assert data_bid1["bid"]["carrier_name"] == "Maersk"  # Derived!
        assert data_bid1["bid"]["total_price"] == "50000.00"
        assert data_bid1["rank"] == 1
        assert data_bid1["extended"] is False

        # 4. Same supplier must bid strictly lower
        res_higher = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_a["id"],
                "freight_charges": "45000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_higher.status_code == 422
        assert res_higher.json()["error"]["code"] == "BID_NOT_LOWER"

        # 5. Same supplier equal bid is also rejected
        res_equal = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_a["id"],
                "freight_charges": "40000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_equal.status_code == 422
        assert res_equal.json()["error"]["code"] == "BID_NOT_LOWER"

        # 6. Another supplier may bid higher than L1 (as long as it's their own best)
        fake_clock.advance(minutes=1)
        res_bid2 = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_b["id"],
                "freight_charges": "45000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_bid2.status_code == 201
        assert res_bid2.json()["rank"] == 2
        assert res_bid2.json()["bid"]["total_price"] == "55000.00"

        # Advance to trigger window: 17:55:00 (Window is [17:50:00, 18:00:00))
        fake_clock.set_time(t_close - timedelta(minutes=5))

        # 7. B bids 48000.00 (beats A's 50000.00, changes L1) -> EXTENDS!
        res_bid3 = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_b["id"],
                "freight_charges": "38000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_bid3.status_code == 201
        data_bid3 = res_bid3.json()
        assert data_bid3["rank"] == 1
        assert data_bid3["extended"] is True
        # Close moved from 18:00 to 18:05
        assert data_bid3["new_close_time"] == "2026-11-20T18:05:00Z"
        assert "L1 changed from Maersk to DHL" in data_bid3["extension_reason"]

        # 8. B improves own price to 47000.00 inside window -> B is already L1, NO extension
        fake_clock.set_time(datetime(2026, 11, 20, 18, 1, 0, tzinfo=timezone.utc))
        res_bid4 = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_b["id"],
                "freight_charges": "37000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_bid4.status_code == 201
        assert res_bid4.json()["extended"] is False
        assert res_bid4.json()["new_close_time"] == "2026-11-20T18:05:00Z"

        # 9. Verify details page ranking & stats
        res_detail = client.get(f"/api/v1/rfqs/{rfq_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["status"] == "ACTIVE"
        assert len(detail["ranking"]) == 2
        assert detail["ranking"][0]["rank"] == 1
        assert detail["ranking"][0]["carrier_name"] == "DHL"
        assert detail["ranking"][0]["total_price"] == "47000.00"
        assert detail["ranking"][1]["rank"] == 2
        assert detail["ranking"][1]["carrier_name"] == "Maersk"
        assert detail["ranking"][1]["total_price"] == "50000.00"

        # Stats
        stats = detail["stats"]
        assert stats["total_bids"] == 4
        assert stats["suppliers_bidding"] == 2
        assert stats["extension_count"] == 1
        assert stats["first_bid_price"] == "50000.00"
        assert stats["current_lowest_price"] == "47000.00"
        # Improvement: (50000 - 47000) / 50000 * 100 = 6.00%
        assert stats["price_improvement_pct"] == "6.00"

        # 10. Advance clock past close (18:06:00) -> bid rejected
        fake_clock.set_time(datetime(2026, 11, 20, 18, 6, 0, tzinfo=timezone.utc))
        res_late = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "supplier_id": s_a["id"],
                "freight_charges": "30000.00",
                "origin_charges": "5000.00",
                "destination_charges": "5000.00",
                "transit_time_days": 10,
                "quote_validity_days": 30,
            },
        )
        assert res_late.status_code == 409
        assert res_late.json()["error"]["code"] == "AUCTION_CLOSED"

        # Status in GET /rfqs/{id} is now CLOSED
        res_closed = client.get(f"/api/v1/rfqs/{rfq_id}")
        assert res_closed.json()["status"] == "CLOSED"
