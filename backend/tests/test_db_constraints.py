from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


class TestDatabaseCheckConstraints:
    def test_rfq_forced_after_original_check(self, test_db):
        rfq_id = str(uuid.uuid4())
        # forced <= original should violate chk_forced_after_original
        sql = text("""
            INSERT INTO rfqs (
                id, reference_id, name, currency, auction_type,
                bid_start_time, original_close_time, current_close_time, forced_close_time,
                status, created_at
            ) VALUES (
                :id, 'CHK-1', 'Test', 'INR', 'STANDARD',
                '2026-11-20 10:00:00', '2026-11-20 18:00:00', '2026-11-20 18:00:00', '2026-11-20 17:50:00',
                'SCHEDULED', '2026-11-14 00:00:00'
            )
        """)
        with pytest.raises(IntegrityError):
            test_db.execute(sql, {"id": rfq_id})
            test_db.commit()
        test_db.rollback()

    def test_rfq_original_after_start_check(self, test_db):
        rfq_id = str(uuid.uuid4())
        # original <= start should violate chk_original_after_start
        sql = text("""
            INSERT INTO rfqs (
                id, reference_id, name, currency, auction_type,
                bid_start_time, original_close_time, current_close_time, forced_close_time,
                status, created_at
            ) VALUES (
                :id, 'CHK-2', 'Test', 'INR', 'STANDARD',
                '2026-11-20 10:00:00', '2026-11-20 09:00:00', '2026-11-20 09:00:00', '2026-11-20 18:30:00',
                'SCHEDULED', '2026-11-14 00:00:00'
            )
        """)
        with pytest.raises(IntegrityError):
            test_db.execute(sql, {"id": rfq_id})
            test_db.commit()
        test_db.rollback()

    def test_rfq_current_in_bounds_check(self, test_db):
        rfq_id = str(uuid.uuid4())
        # current > forced should violate chk_current_in_bounds
        sql = text("""
            INSERT INTO rfqs (
                id, reference_id, name, currency, auction_type,
                bid_start_time, original_close_time, current_close_time, forced_close_time,
                status, created_at
            ) VALUES (
                :id, 'CHK-3', 'Test', 'INR', 'STANDARD',
                '2026-11-20 10:00:00', '2026-11-20 18:00:00', '2026-11-20 18:45:00', '2026-11-20 18:30:00',
                'SCHEDULED', '2026-11-14 00:00:00'
            )
        """)
        with pytest.raises(IntegrityError):
            test_db.execute(sql, {"id": rfq_id})
            test_db.commit()
        test_db.rollback()

    def test_bid_negative_charge_check(self, test_db):
        # Setup valid supplier and rfq
        s_id = str(uuid.uuid4())
        rfq_id = str(uuid.uuid4())
        test_db.execute(text("INSERT INTO suppliers (id, name, created_at) VALUES (:s_id, 'Sup-1', '2026-11-14 00:00:00')"), {"s_id": s_id})
        test_db.execute(text("""
            INSERT INTO rfqs (
                id, reference_id, name, currency, auction_type,
                bid_start_time, original_close_time, current_close_time, forced_close_time,
                status, created_at
            ) VALUES (
                :rfq_id, 'CHK-4', 'Test', 'INR', 'STANDARD',
                '2026-11-20 10:00:00', '2026-11-20 18:00:00', '2026-11-20 18:00:00', '2026-11-20 18:30:00',
                'ACTIVE', '2026-11-14 00:00:00'
            )
        """), {"rfq_id": rfq_id})
        test_db.commit()

        # Negative freight charge
        bid_id = str(uuid.uuid4())
        sql = text("""
            INSERT INTO bids (
                id, rfq_id, supplier_id, carrier_name, freight_charges, origin_charges,
                destination_charges, total_price, transit_time_days, quote_validity_days,
                submitted_at
            ) VALUES (
                :bid_id, :rfq_id, :s_id, 'Carrier', -100.00, 50.00,
                50.00, 0.00, 5, 10, '2026-11-20 12:00:00'
            )
        """)
        with pytest.raises(IntegrityError):
            test_db.execute(sql, {"bid_id": bid_id, "rfq_id": rfq_id, "s_id": s_id})
            test_db.commit()
        test_db.rollback()

    def test_bid_total_sum_check(self, test_db):
        s_id = str(uuid.uuid4())
        rfq_id = str(uuid.uuid4())
        test_db.execute(text("INSERT INTO suppliers (id, name, created_at) VALUES (:s_id, 'Sup-2', '2026-11-14 00:00:00')"), {"s_id": s_id})
        test_db.execute(text("""
            INSERT INTO rfqs (
                id, reference_id, name, currency, auction_type,
                bid_start_time, original_close_time, current_close_time, forced_close_time,
                status, created_at
            ) VALUES (
                :rfq_id, 'CHK-5', 'Test', 'INR', 'STANDARD',
                '2026-11-20 10:00:00', '2026-11-20 18:00:00', '2026-11-20 18:00:00', '2026-11-20 18:30:00',
                'ACTIVE', '2026-11-14 00:00:00'
            )
        """), {"rfq_id": rfq_id})
        test_db.commit()

        # Total price does NOT equal sum of freight + origin + destination
        bid_id = str(uuid.uuid4())
        sql = text("""
            INSERT INTO bids (
                id, rfq_id, supplier_id, carrier_name, freight_charges, origin_charges,
                destination_charges, total_price, transit_time_days, quote_validity_days,
                submitted_at
            ) VALUES (
                :bid_id, :rfq_id, :s_id, 'Carrier', 1000.00, 200.00,
                100.00, 9999.00, 5, 10, '2026-11-20 12:00:00'
            )
        """)
        with pytest.raises(IntegrityError):
            test_db.execute(sql, {"bid_id": bid_id, "rfq_id": rfq_id, "s_id": s_id})
            test_db.commit()
        test_db.rollback()

    def test_british_config_xy_positive_checks(self, test_db):
        rfq_id = str(uuid.uuid4())
        test_db.execute(text("""
            INSERT INTO rfqs (
                id, reference_id, name, currency, auction_type,
                bid_start_time, original_close_time, current_close_time, forced_close_time,
                status, created_at
            ) VALUES (
                :rfq_id, 'CHK-6', 'Test', 'INR', 'BRITISH',
                '2026-11-20 10:00:00', '2026-11-20 18:00:00', '2026-11-20 18:00:00', '2026-11-20 18:30:00',
                'ACTIVE', '2026-11-14 00:00:00'
            )
        """), {"rfq_id": rfq_id})
        test_db.commit()

        # trigger_window_minutes = 0 should violate chk_trigger_window_positive
        sql = text("""
            INSERT INTO british_auction_configs (
                rfq_id, trigger_window_minutes, extension_minutes, extension_trigger
            ) VALUES (
                :rfq_id, 0, 5, 'BID_IN_LAST_X'
            )
        """)
        with pytest.raises(IntegrityError):
            test_db.execute(sql, {"rfq_id": rfq_id})
            test_db.commit()
        test_db.rollback()
