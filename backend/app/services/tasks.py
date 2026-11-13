from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import or_, select

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.entities import RFQ
from app.models.enums import AuctionStatus
from app.services.auction_engine import derive_status
from app.services.lifecycle_service import ensure_lifecycle_events

try:
    from celery.signals import worker_ready
except ImportError:
    class MockSignal:
        def connect(self, fn):
            return fn
    worker_ready = MockSignal()


def run_sweeper(db_session=None, current_time: Optional[datetime] = None) -> int:
    """
    Core sweeping logic: finds all auctions whose stored cached status
    differs from their derived status or whose close time has arrived,
    and runs ensure_lifecycle_events under lock.
    Returns the number of auctions processed.
    """
    now = current_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    session = db_session or SessionLocal()
    processed_count = 0
    try:
        # Select candidate RFQs:
        # 1. Scheduled but start time reached
        # 2. Active but close time reached
        # 3. Any whose cached status != derived
        stmt = select(RFQ).where(
            or_(
                RFQ.status == AuctionStatus.SCHEDULED,
                RFQ.status == AuctionStatus.ACTIVE,
            )
        )
        if session.bind and session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        candidates = session.execute(stmt).scalars().all()

        for rfq in candidates:
            derived = derive_status(
                bid_start_time=rfq.bid_start_time,
                current_close_time=rfq.current_close_time,
                forced_close_time=rfq.forced_close_time,
                now=now,
            )
            # Process if status changed or close time reached
            if derived != rfq.status or now >= rfq.current_close_time:
                ensure_lifecycle_events(rfq, now, session)
                processed_count += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if db_session is None:
            session.close()

    return processed_count


@celery_app.task(name="app.services.tasks.finalize_due_auctions")
def finalize_due_auctions() -> int:
    """Periodic celery task running every 5 seconds."""
    return run_sweeper()


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Executes catch-up immediately when Celery worker boots up."""
    print("Celery worker ready — running immediate lifecycle catch-up...")
    try:
        run_sweeper()
    except Exception as e:
        print(f"Error during worker_ready catch-up: {e}")
