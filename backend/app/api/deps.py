from app.db.session import get_db
from app.services.clock import Clock, SystemClock

__all__ = ["get_db", "get_clock", "Clock", "SystemClock"]

_system_clock = SystemClock()


def get_clock() -> Clock:
    """Provides clock dependency; easily overridden in tests with FakeClock."""
    return _system_clock

