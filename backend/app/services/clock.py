from datetime import datetime, timezone, timedelta
from typing import Protocol


class Clock(Protocol):
    """Protocol for time providers, allowing clock injection for deterministic tests."""
    def now(self) -> datetime:
        ...


class SystemClock:
    """Production clock using standard UTC time."""
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """Controllable clock for unit and integration testing."""
    def __init__(self, initial_time: datetime):
        if initial_time.tzinfo is None:
            self._current_time = initial_time.replace(tzinfo=timezone.utc)
        else:
            self._current_time = initial_time.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._current_time

    def set_time(self, new_time: datetime) -> None:
        if new_time.tzinfo is None:
            self._current_time = new_time.replace(tzinfo=timezone.utc)
        else:
            self._current_time = new_time.astimezone(timezone.utc)

    def advance(self, **kwargs) -> datetime:
        """Advance time using timedelta parameters (e.g. minutes=5, seconds=10)."""
        self._current_time += timedelta(**kwargs)
        return self._current_time

