from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.enums import AuctionEventType


class AuctionEventItem(BaseModel):
    id: UUID
    event_type: AuctionEventType
    bid_id: Optional[UUID] = None
    payload: dict[str, Any]
    reason: str
    occurred_at: datetime
    created_at: datetime
    is_recovered: bool

    model_config = ConfigDict(from_attributes=True)


class AuctionEventListResponse(BaseModel):
    items: list[AuctionEventItem]
    total: int
    page: int
    page_size: int
    server_time: datetime

