from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

from app.models.enums import AuctionEventType, AuctionStatus, ExtensionTrigger


class InvalidTransitionError(Exception):
    """Raised when an illegal auction status transition is attempted."""
    def __init__(self, from_status: AuctionStatus, to_status: AuctionStatus):
        super().__init__(f"Invalid transition from {from_status} to {to_status}")
        self.from_status = from_status
        self.to_status = to_status


ALLOWED_TRANSITIONS: set[tuple[AuctionStatus, AuctionStatus]] = {
    (AuctionStatus.SCHEDULED, AuctionStatus.ACTIVE),
    (AuctionStatus.ACTIVE, AuctionStatus.CLOSED),
    (AuctionStatus.ACTIVE, AuctionStatus.FORCE_CLOSED),
    (AuctionStatus.ACTIVE, AuctionStatus.ACTIVE),  # Self-loop: time extended
}


def assert_transition(from_status: AuctionStatus, to_status: AuctionStatus) -> None:
    """
    Validates state machine transitions.
    CLOSED and FORCE_CLOSED are terminal.
    Same-to-same is a no-op (idempotent).
    """
    if from_status == to_status:
        return
    if (from_status, to_status) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(from_status, to_status)


def derive_status(
    bid_start_time: datetime,
    current_close_time: datetime,
    forced_close_time: datetime,
    now: datetime,
) -> AuctionStatus:
    """
    Pure function: derives status strictly from timestamps.
    Never relies on stored cached status.
    """
    # Ensure all timestamps are UTC-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if bid_start_time.tzinfo is None:
        bid_start_time = bid_start_time.replace(tzinfo=timezone.utc)
    if current_close_time.tzinfo is None:
        current_close_time = current_close_time.replace(tzinfo=timezone.utc)
    if forced_close_time.tzinfo is None:
        forced_close_time = forced_close_time.replace(tzinfo=timezone.utc)

    if now < bid_start_time:
        return AuctionStatus.SCHEDULED
    if now < current_close_time:
        return AuctionStatus.ACTIVE
    if current_close_time == forced_close_time:
        return AuctionStatus.FORCE_CLOSED
    return AuctionStatus.CLOSED


@dataclass(frozen=True)
class BidSnapshot:
    id: UUID | str
    supplier_id: UUID | str
    carrier_name: str
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total_price: Decimal
    transit_time_days: int
    quote_validity_days: int
    submitted_at: datetime


@dataclass(frozen=True)
class SupplierRank:
    rank: int
    supplier_id: UUID | str
    carrier_name: str
    best_bid: BidSnapshot


def _get_val(obj: Any, key: str) -> Any:
    """Helper to extract field from either an ORM entity or a dictionary."""
    if isinstance(obj, dict):
        return obj[key]
    val = getattr(obj, key, None)
    if val is not None:
        return val
    # Fallback if obj implements __getitem__
    if hasattr(obj, "__getitem__"):
        try:
            return obj[key]
        except (KeyError, TypeError):
            pass
    return None


def compute_ranking(bids: Sequence[Any]) -> list[SupplierRank]:
    """
    Computes ranking based on each supplier's best (lowest total_price) bid.
    Sort key: (total_price ASC, submitted_at ASC, bid_id ASC).
    The earlier bid wins ties.
    Returns list of SupplierRank ordered from L1 (rank 1) downwards.
    """
    # Group by supplier_id and pick lowest total_price
    best_bids_by_supplier: dict[Any, Any] = {}

    for b in bids:
        supplier_id = _get_val(b, "supplier_id")
        total_price = Decimal(str(_get_val(b, "total_price")))
        submitted_at = _get_val(b, "submitted_at")
        bid_id = str(_get_val(b, "id"))

        current_best = best_bids_by_supplier.get(supplier_id)
        if current_best is None:
            best_bids_by_supplier[supplier_id] = b
        else:
            cb_price = Decimal(str(_get_val(current_best, "total_price")))
            cb_time = _get_val(current_best, "submitted_at")
            cb_id = str(_get_val(current_best, "id"))

            new_tuple = (total_price, submitted_at, bid_id)
            cb_tuple = (cb_price, cb_time, cb_id)
            if new_tuple < cb_tuple:
                best_bids_by_supplier[supplier_id] = b

    # Sort suppliers by their best bid
    def sort_key(item: tuple[Any, Any]):
        b = item[1]
        t = Decimal(str(_get_val(b, "total_price")))
        s = _get_val(b, "submitted_at")
        i = str(_get_val(b, "id"))
        return (t, s, i)

    sorted_suppliers = sorted(best_bids_by_supplier.items(), key=sort_key)

    ranking: list[SupplierRank] = []
    for rank_idx, (supplier_id, b) in enumerate(sorted_suppliers, start=1):
        snapshot = BidSnapshot(
            id=_get_val(b, "id"),
            supplier_id=supplier_id,
            carrier_name=_get_val(b, "carrier_name"),
            freight_charges=Decimal(str(_get_val(b, "freight_charges"))),
            origin_charges=Decimal(str(_get_val(b, "origin_charges"))),
            destination_charges=Decimal(str(_get_val(b, "destination_charges"))),
            total_price=Decimal(str(_get_val(b, "total_price"))),
            transit_time_days=int(_get_val(b, "transit_time_days")),
            quote_validity_days=int(_get_val(b, "quote_validity_days")),
            submitted_at=_get_val(b, "submitted_at"),
        )
        ranking.append(SupplierRank(
            rank=rank_idx,
            supplier_id=supplier_id,
            carrier_name=snapshot.carrier_name,
            best_bid=snapshot,
        ))

    return ranking


def in_trigger_window(
    current_close_time: datetime,
    trigger_window_minutes: int,
    now: datetime,
) -> bool:
    """
    Trigger window is [current_close - X, current_close): inclusive start, exclusive end.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if current_close_time.tzinfo is None:
        current_close_time = current_close_time.replace(tzinfo=timezone.utc)

    window_start = current_close_time - timedelta(minutes=trigger_window_minutes)
    return window_start <= now < current_close_time


def evaluate_trigger(
    trigger_type: ExtensionTrigger,
    ranking_before: Sequence[SupplierRank],
    ranking_after: Sequence[SupplierRank],
    new_bid: Any | None = None,
) -> bool:
    """
    Evaluates whether an extension should be triggered based on ranking change:
    - BID_IN_LAST_X: any bid accepted in window triggers extension (True)
    - ANY_RANK_CHANGE_IN_LAST_X: ordered list of supplier_ids before != after
    - L1_CHANGE_IN_LAST_X: top supplier before != top supplier after (first bid counts)
    """
    if trigger_type == ExtensionTrigger.BID_IN_LAST_X:
        return True

    suppliers_before = [r.supplier_id for r in ranking_before]
    suppliers_after = [r.supplier_id for r in ranking_after]

    if trigger_type == ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X:
        # A new supplier entering changes the list -> triggers.
        # A supplier improving their price without changing position leaves the list equal -> False.
        return suppliers_before != suppliers_after

    if trigger_type == ExtensionTrigger.L1_CHANGE_IN_LAST_X:
        # If no prior L1 existed (first ever bid), L1 has changed from None to the bidder -> True
        if not suppliers_before:
            return bool(suppliers_after)
        # If top supplier changed -> True.
        # If current L1 improves own price, top supplier before == after -> False.
        return suppliers_before[0] != suppliers_after[0]

    return False


def compute_extension(
    current_close_time: datetime,
    extension_minutes: int,
    forced_close_time: datetime,
) -> tuple[datetime, bool]:
    """
    Extension is added to CURRENT close time, never beyond forced close.
    new_close = min(current_close + Y, forced_close).
    Returns (new_close_time, was_extended).
    was_extended is True only if new_close_time > current_close_time.
    """
    if current_close_time.tzinfo is None:
        current_close_time = current_close_time.replace(tzinfo=timezone.utc)
    if forced_close_time.tzinfo is None:
        forced_close_time = forced_close_time.replace(tzinfo=timezone.utc)

    proposed_close = current_close_time + timedelta(minutes=extension_minutes)
    new_close = min(proposed_close, forced_close_time)
    was_extended = new_close > current_close_time
    return new_close, was_extended


def due_lifecycle_events(
    bid_start_time: datetime,
    current_close_time: datetime,
    forced_close_time: datetime,
    existing_event_types: set[AuctionEventType],
    now: datetime,
) -> list[tuple[AuctionEventType, datetime]]:
    """
    Computes which lifecycle events are due as of `now` but have not yet been recorded.
    Returns list of (event_type, logical_occurred_at) in chronological order.
    Ensures multi-transition catch-up (e.g. AUCTION_STARTED and then AUCTION_CLOSED).
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if bid_start_time.tzinfo is None:
        bid_start_time = bid_start_time.replace(tzinfo=timezone.utc)
    if current_close_time.tzinfo is None:
        current_close_time = current_close_time.replace(tzinfo=timezone.utc)
    if forced_close_time.tzinfo is None:
        forced_close_time = forced_close_time.replace(tzinfo=timezone.utc)

    events: list[tuple[AuctionEventType, datetime]] = []

    # 1. AUCTION_STARTED
    if now >= bid_start_time and AuctionEventType.AUCTION_STARTED not in existing_event_types:
        events.append((AuctionEventType.AUCTION_STARTED, bid_start_time))

    # 2. AUCTION_CLOSED or AUCTION_FORCE_CLOSED
    if now >= current_close_time:
        if current_close_time == forced_close_time:
            target_close_event = AuctionEventType.AUCTION_FORCE_CLOSED
        else:
            target_close_event = AuctionEventType.AUCTION_CLOSED

        if target_close_event not in existing_event_types:
            events.append((target_close_event, current_close_time))

    # Sort strictly by occurred_at
    events.sort(key=lambda x: x[1])
    return events


def generate_extension_reason(
    trigger_type: ExtensionTrigger,
    current_l1_name: str,
    previous_l1_name: str | None,
    occurred_at: datetime,
    old_close: datetime,
    new_close: datetime,
    window_minutes: int,
) -> str:
    """
    Generates human-readable explanation for an extension event.
    Example:
    'L1 changed from Maersk to DHL at 5:55:00 PM, inside the last 10 min window. Close moved 6:00 PM → 6:05 PM.'
    """
    time_str = occurred_at.strftime("%I:%M:%S %p")
    old_close_str = old_close.strftime("%I:%M %p")
    new_close_str = new_close.strftime("%I:%M %p")

    if trigger_type == ExtensionTrigger.L1_CHANGE_IN_LAST_X:
        if previous_l1_name:
            subject = f"L1 changed from {previous_l1_name} to {current_l1_name}"
        else:
            subject = f"{current_l1_name} set initial L1"
    elif trigger_type == ExtensionTrigger.ANY_RANK_CHANGE_IN_LAST_X:
        subject = f"Supplier ranking changed (bid placed by {current_l1_name})"
    else:  # BID_IN_LAST_X
        subject = f"Bid placed by {current_l1_name}"

    return (
        f"{subject} at {time_str}, inside the last {window_minutes} min window. "
        f"Close moved {old_close_str} → {new_close_str}."
    )

