from datetime import datetime, timezone, timedelta
from app.services.clock import FakeClock, SystemClock


def test_system_clock():
    clock = SystemClock()
    t = clock.now()
    assert t.tzinfo is not None
    assert isinstance(t, datetime)


def test_fake_clock_advance_and_set():
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
    clock = FakeClock(t0)
    assert clock.now() == t0

    # Advance 15 minutes
    clock.advance(minutes=15)
    assert clock.now() == datetime(2026, 11, 20, 12, 15, 0, tzinfo=timezone.utc)

    # Set time directly
    t1 = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
    clock.set_time(t1)
    assert clock.now() == t1

