from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
import uuid
import pytest

from app.models.enums import AuctionEventType, AuctionStatus, ExtensionTrigger
from app.services.auction_engine import (
    derive_status,
    compute_ranking,
    in_trigger_window,
    evaluate_trigger,
    compute_extension,
    due_lifecycle_events,
    generate_extension_reason,
)


@pytest.fixture
def base_times():
    start = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    close = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
    forced = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)
    return start, close, forced


class TestDeriveStatus:
    def test_scheduled_before_start(self, base_times):
        start, close, forced = base_times
        now = start - timedelta(seconds=1)
        assert derive_status(start, close, forced, now) == AuctionStatus.SCHEDULED

    def test_active_at_exact_start(self, base_times):
        start, close, forced = base_times
        now = start
        assert derive_status(start, close, forced, now) == AuctionStatus.ACTIVE

    def test_active_between_start_and_close(self, base_times):
        start, close, forced = base_times
        now = start + timedelta(hours=2)
        assert derive_status(start, close, forced, now) == AuctionStatus.ACTIVE

    def test_active_just_before_close(self, base_times):
        start, close, forced = base_times
        now = close - timedelta(microseconds=1)
        assert derive_status(start, close, forced, now) == AuctionStatus.ACTIVE

    def test_closed_at_exact_close(self, base_times):
        start, close, forced = base_times
        now = close
        assert derive_status(start, close, forced, now) == AuctionStatus.CLOSED

    def test_closed_after_close(self, base_times):
        start, close, forced = base_times
        now = close + timedelta(minutes=5)
        assert derive_status(start, close, forced, now) == AuctionStatus.CLOSED

    def test_force_closed_at_exact_forced_close(self, base_times):
        start, _, forced = base_times
        # If current_close was extended all the way to forced
        current_close = forced
        now = forced
        assert derive_status(start, current_close, forced, now) == AuctionStatus.FORCE_CLOSED

    def test_force_closed_after_forced_close(self, base_times):
        start, _, forced = base_times
        current_close = forced
        now = forced + timedelta(minutes=10)
        assert derive_status(start, current_close, forced, now) == AuctionStatus.FORCE_CLOSED


class TestComputeRanking:
    def test_empty_bids(self):
        assert compute_ranking([]) == []

    def test_supplier_best_bid_deduplication(self):
        # Supplier A bids 50000 -> 48000 -> 45000
        # Supplier B bids 47000 -> 46000
        # Supplier C bids 49000
        supplier_a = uuid.uuid4()
        supplier_b = uuid.uuid4()
        supplier_c = uuid.uuid4()
        t0 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)

        bids = [
            {
                "id": uuid.uuid4(),
                "supplier_id": supplier_a,
                "carrier_name": "Carrier A",
                "freight_charges": "40000",
                "origin_charges": "5000",
                "destination_charges": "5000",
                "total_price": "50000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(minutes=1),
            },
            {
                "id": uuid.uuid4(),
                "supplier_id": supplier_b,
                "carrier_name": "Carrier B",
                "freight_charges": "38000",
                "origin_charges": "5000",
                "destination_charges": "4000",
                "total_price": "47000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(minutes=2),
            },
            {
                "id": uuid.uuid4(),
                "supplier_id": supplier_a,
                "carrier_name": "Carrier A",
                "freight_charges": "38000",
                "origin_charges": "5000",
                "destination_charges": "5000",
                "total_price": "48000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(minutes=3),
            },
            {
                "id": uuid.uuid4(),
                "supplier_id": supplier_c,
                "carrier_name": "Carrier C",
                "freight_charges": "39000",
                "origin_charges": "5000",
                "destination_charges": "5000",
                "total_price": "49000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(minutes=4),
            },
            {
                "id": uuid.uuid4(),
                "supplier_id": supplier_b,
                "carrier_name": "Carrier B",
                "freight_charges": "37000",
                "origin_charges": "5000",
                "destination_charges": "4000",
                "total_price": "46000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(minutes=5),
            },
            {
                "id": uuid.uuid4(),
                "supplier_id": supplier_a,
                "carrier_name": "Carrier A",
                "freight_charges": "35000",
                "origin_charges": "5000",
                "destination_charges": "5000",
                "total_price": "45000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(minutes=6),
            },
        ]

        ranking = compute_ranking(bids)
        assert len(ranking) == 3

        # Rank 1: Supplier A with 45000
        assert ranking[0].rank == 1
        assert ranking[0].supplier_id == supplier_a
        assert ranking[0].best_bid.total_price == Decimal("45000")

        # Rank 2: Supplier B with 46000
        assert ranking[1].rank == 2
        assert ranking[1].supplier_id == supplier_b
        assert ranking[1].best_bid.total_price == Decimal("46000")

        # Rank 3: Supplier C with 49000
        assert ranking[2].rank == 3
        assert ranking[2].supplier_id == supplier_c
        assert ranking[2].best_bid.total_price == Decimal("49000")

    def test_ranking_tie_breaks_earlier_bid_wins(self):
        supplier_x = uuid.uuid4()
        supplier_y = uuid.uuid4()
        t0 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)

        bids = [
            {
                "id": "bid-2",
                "supplier_id": supplier_y,
                "carrier_name": "Carrier Y",
                "freight_charges": "50000",
                "origin_charges": "0",
                "destination_charges": "0",
                "total_price": "50000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(seconds=10),
            },
            {
                "id": "bid-1",
                "supplier_id": supplier_x,
                "carrier_name": "Carrier X",
                "freight_charges": "50000",
                "origin_charges": "0",
                "destination_charges": "0",
                "total_price": "50000",
                "transit_time_days": 10,
                "quote_validity_days": 30,
                "submitted_at": t0 + timedelta(seconds=5),  # Earlier!
            },
        ]

        ranking = compute_ranking(bids)
        assert ranking[0].supplier_id == supplier_x
        assert ranking[1].supplier_id == supplier_y


class TestInTriggerWindow:
    def test_boundaries(self):
        close = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
        x_min = 10  # Window: [17:50:00, 18:00:00)

        # 1s before window: 17:49:59 -> False
        assert in_trigger_window(close, x_min, close - timedelta(minutes=10, seconds=1)) is False

        # Exact window start: 17:50:00 -> True (inclusive)
        assert in_trigger_window(close, x_min, close - timedelta(minutes=10)) is True

        # Mid-window: 17:55:00 -> True
        assert in_trigger_window(close, x_min, close - timedelta(minutes=5)) is True

        # Exact close: 18:00:00 -> False (exclusive, auction already closed)
        assert in_trigger_window(close, x_min, close) is False

        # Past close: 18:01:00 -> False
        assert in_trigger_window(close, x_min, close + timedelta(minutes=1)) is False


class TestEvaluateTrigger:
    def _make_rank(self, rank_num: int, supplier_id: Any, total_price: str):
        from app.services.auction_engine import SupplierRank, BidSnapshot
        return SupplierRank(
            rank=rank_num,
            supplier_id=supplier_id,
            carrier_name=f"Carrier {supplier_id}",
            best_bid=BidSnapshot(
                id=uuid.uuid4(),
                supplier_id=supplier_id,
                carrier_name=f"Carrier {supplier_id}",
                freight_charges=Decimal(total_price),
                origin_charges=Decimal("0"),
                destination_charges=Decimal("0"),
                total_price=Decimal(total_price),
                transit_time_days=5,
                quote_validity_days=10,
                submitted_at=datetime.now(timezone.utc),
            )
        )

    def test_bid_in_last_x_always_triggers(self):
        before = [self._make_rank(1, "A", "1000")]
        after = [self._make_rank(1, "A", "900")]
        assert evaluate_trigger(ExtensionTrigger.BID_IN_LAST_X, before, after) is True

    def test_any_rank_change_trigger(self):
        s_a, s_b = "A", "B"

        # Case 1: First ever bid (empty -> [A])
        assert evaluate_trigger(ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X, [], [self._make_rank(1, s_a, "1000")]) is True

        # Case 2: New supplier B enters behind A ([A] -> [A, B]) -> rank list changed
        before = [self._make_rank(1, s_a, "1000")]
        after = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1050")]
        assert evaluate_trigger(ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X, before, after) is True

        # Case 3: Supplier B underbids A ([A, B] -> [B, A]) -> rank changed
        before = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1050")]
        after = [self._make_rank(1, s_b, "950"), self._make_rank(2, s_a, "1000")]
        assert evaluate_trigger(ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X, before, after) is True

        # Case 4: Supplier A improves price, remains L1 ([A, B] -> [A, B]) -> NO rank change
        before = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1050")]
        after = [self._make_rank(1, s_a, "980"), self._make_rank(2, s_b, "1050")]
        assert evaluate_trigger(ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X, before, after) is False

        # Case 5: Supplier B improves price, remains L2 ([A, B] -> [A, B]) -> NO rank change
        before = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1050")]
        after = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1020")]
        assert evaluate_trigger(ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X, before, after) is False

    def test_l1_change_trigger(self):
        s_a, s_b, s_c = "A", "B", "C"

        # Case 1: First ever bid (None -> A) -> counts as L1 change
        assert evaluate_trigger(ExtensionTrigger.L1_CHANGE_IN_LAST_X, [], [self._make_rank(1, s_a, "1000")]) is True

        # Case 2: Supplier B bids lower than A (L1 changes from A to B) -> True
        before = [self._make_rank(1, s_a, "1000")]
        after = [self._make_rank(1, s_b, "950"), self._make_rank(2, s_a, "1000")]
        assert evaluate_trigger(ExtensionTrigger.L1_CHANGE_IN_LAST_X, before, after) is True

        # Case 3: Supplier A (current L1) improves own price -> False (L1 did not change)
        before = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1050")]
        after = [self._make_rank(1, s_a, "900"), self._make_rank(2, s_b, "1050")]
        assert evaluate_trigger(ExtensionTrigger.L1_CHANGE_IN_LAST_X, before, after) is False

        # Case 4: Supplier C joins as rank 3 or rank 2 without taking L1 -> False
        before = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_b, "1050")]
        after = [self._make_rank(1, s_a, "1000"), self._make_rank(2, s_c, "1020"), self._make_rank(3, s_b, "1050")]
        assert evaluate_trigger(ExtensionTrigger.L1_CHANGE_IN_LAST_X, before, after) is False


class TestComputeExtension:
    def test_standard_extension(self):
        current_close = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
        forced_close = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)
        extension_min = 5

        new_close, extended = compute_extension(current_close, extension_min, forced_close)
        assert extended is True
        assert new_close == datetime(2026, 11, 20, 18, 5, 0, tzinfo=timezone.utc)

    def test_extension_capped_at_forced_close(self):
        # 18:28 + 5 min = 18:33, capped at 18:30
        current_close = datetime(2026, 11, 20, 18, 28, 0, tzinfo=timezone.utc)
        forced_close = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)
        extension_min = 5

        new_close, extended = compute_extension(current_close, extension_min, forced_close)
        assert extended is True
        assert new_close == forced_close

    def test_extension_at_cap_is_skipped(self):
        # Already at 18:30
        current_close = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)
        forced_close = datetime(2026, 11, 20, 18, 30, 0, tzinfo=timezone.utc)
        extension_min = 5

        new_close, extended = compute_extension(current_close, extension_min, forced_close)
        assert extended is False
        assert new_close == forced_close


class TestDueLifecycleEvents:
    def test_before_start_no_events(self, base_times):
        start, close, forced = base_times
        now = start - timedelta(minutes=10)
        events = due_lifecycle_events(start, close, forced, set(), now)
        assert events == []

    def test_at_start_emits_auction_started(self, base_times):
        start, close, forced = base_times
        now = start
        events = due_lifecycle_events(start, close, forced, set(), now)
        assert events == [(AuctionEventType.AUCTION_STARTED, start)]

    def test_already_started_does_not_duplicate(self, base_times):
        start, close, forced = base_times
        now = start + timedelta(hours=1)
        events = due_lifecycle_events(start, close, forced, {AuctionEventType.AUCTION_STARTED}, now)
        assert events == []

    def test_multi_transition_recovery_during_outage(self, base_times):
        # Auction started at 10:00, closed at 18:00
        # Sweeper runs for the first time at 18:10 (both events missed)
        start, close, forced = base_times
        now = close + timedelta(minutes=10)
        events = due_lifecycle_events(start, close, forced, set(), now)

        assert len(events) == 2
        assert events[0] == (AuctionEventType.AUCTION_STARTED, start)
        assert events[1] == (AuctionEventType.AUCTION_CLOSED, close)

    def test_force_closed_event_when_close_equals_forced(self, base_times):
        start, _, forced = base_times
        current_close = forced
        now = forced + timedelta(minutes=5)

        events = due_lifecycle_events(start, current_close, forced, {AuctionEventType.AUCTION_STARTED}, now)
        assert len(events) == 1
        assert events[0] == (AuctionEventType.AUCTION_FORCE_CLOSED, forced)


class TestExtensionReasonString:
    def test_reason_generation(self):
        t = datetime(2026, 11, 20, 17, 55, 12, tzinfo=timezone.utc)
        old_close = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
        new_close = datetime(2026, 11, 20, 18, 5, 0, tzinfo=timezone.utc)

        reason = generate_extension_reason(
            trigger_type=ExtensionTrigger.L1_CHANGE_IN_LAST_X,
            current_l1_name="DHL",
            previous_l1_name="Maersk",
            occurred_at=t,
            old_close=old_close,
            new_close=new_close,
            window_minutes=10,
        )
        assert "L1 changed from Maersk to DHL" in reason
        assert "05:55:12 PM" in reason
        assert "inside the last 10 min window" in reason
        assert "06:00 PM" in reason
        assert "06:05 PM" in reason
