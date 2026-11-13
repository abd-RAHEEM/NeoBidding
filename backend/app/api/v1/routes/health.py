from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_db
from app.services.clock import Clock

router = APIRouter()


@router.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db), clock: Clock = Depends(get_clock)):
    now = clock.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "time": now.isoformat(),
    }

