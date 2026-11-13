import pytest
from app.models.enums import AuctionStatus
from app.services.auction_engine import assert_transition, InvalidTransitionError


class TestStateMachine:
    def test_valid_transitions(self):
        # SCHEDULED -> ACTIVE
        assert_transition(AuctionStatus.SCHEDULED, AuctionStatus.ACTIVE)

        # ACTIVE -> CLOSED
        assert_transition(AuctionStatus.ACTIVE, AuctionStatus.CLOSED)

        # ACTIVE -> FORCE_CLOSED
        assert_transition(AuctionStatus.ACTIVE, AuctionStatus.FORCE_CLOSED)

        # ACTIVE -> ACTIVE (self-loop for time extension)
        assert_transition(AuctionStatus.ACTIVE, AuctionStatus.ACTIVE)

    def test_idempotent_same_state_transitions(self):
        # All same-to-same transitions are allowed no-ops
        for status in AuctionStatus:
            assert_transition(status, status)

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (AuctionStatus.SCHEDULED, AuctionStatus.CLOSED),
            (AuctionStatus.SCHEDULED, AuctionStatus.FORCE_CLOSED),
            (AuctionStatus.CLOSED, AuctionStatus.ACTIVE),
            (AuctionStatus.CLOSED, AuctionStatus.SCHEDULED),
            (AuctionStatus.CLOSED, AuctionStatus.FORCE_CLOSED),
            (AuctionStatus.FORCE_CLOSED, AuctionStatus.ACTIVE),
            (AuctionStatus.FORCE_CLOSED, AuctionStatus.SCHEDULED),
            (AuctionStatus.FORCE_CLOSED, AuctionStatus.CLOSED),
            (AuctionStatus.ACTIVE, AuctionStatus.SCHEDULED),
        ],
    )
    def test_invalid_transitions(self, from_status, to_status):
        with pytest.raises(InvalidTransitionError) as exc_info:
            assert_transition(from_status, to_status)
        assert exc_info.value.from_status == from_status
        assert exc_info.value.to_status == to_status

