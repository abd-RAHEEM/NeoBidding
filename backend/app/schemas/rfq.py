from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.models.enums import AuctionStatus, AuctionType, ExtensionTrigger
from app.schemas.bid import BidRecord, serialize_decimal, serialize_utc_datetime
from app.schemas.event import AuctionEventItem
from app.schemas.supplier import SupplierResponse


class BritishConfigSchema(BaseModel):
    trigger_window_minutes: int = Field(..., ge=1, description="Trigger window X in minutes (>= 1)")
    extension_minutes: int = Field(..., ge=1, description="Extension duration Y in minutes (>= 1)")
    extension_trigger: ExtensionTrigger

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data):
        if isinstance(data, dict):
            if "extension_duration_minutes" in data and "extension_minutes" not in data:
                data["extension_minutes"] = data["extension_duration_minutes"]
        return data

    model_config = ConfigDict(from_attributes=True)


class RFQCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    reference_id: str = Field(..., min_length=1, max_length=64)
    currency: str = Field("INR", pattern="^(INR|USD|EUR|GBP|AED)$")
    pickup_date: Optional[date] = None
    auction_type: AuctionType = AuctionType.STANDARD
    bid_start_time: datetime
    bid_close_time: datetime
    forced_close_time: datetime
    invited_supplier_ids: list[UUID] = Field(..., min_length=1, description="At least one invited supplier is required")
    british_config: Optional[BritishConfigSchema] = None

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data):
        if isinstance(data, dict):
            if "supplier_ids" in data and "invited_supplier_ids" not in data:
                data["invited_supplier_ids"] = data["supplier_ids"]
            if "mode" in data and "auction_type" not in data:
                data["auction_type"] = data["mode"]
        return data

    @model_validator(mode="after")
    def validate_rfq_times_and_config(self) -> "RFQCreate":
        if self.bid_close_time <= self.bid_start_time:
            raise ValueError("Bid Close Time must be strictly greater than Bid Start Time.")
        if self.forced_close_time <= self.bid_close_time:
            raise ValueError("Forced Bid Close Time must be strictly greater than Bid Close Time.")

        if self.auction_type == AuctionType.BRITISH:
            if self.british_config is None:
                raise ValueError("british_config is required when auction_type is BRITISH.")
        else:
            if self.british_config is not None:
                raise ValueError("british_config must not be provided when auction_type is STANDARD.")

        return self


class RFQListItem(BaseModel):
    id: UUID
    reference_id: str
    name: str
    currency: str
    auction_type: AuctionType
    current_lowest_bid: Optional[Decimal] = None
    bid_start_time: datetime
    original_close_time: datetime
    current_close_time: datetime
    forced_close_time: datetime
    status: AuctionStatus

    @field_serializer("current_lowest_bid")
    def serialize_price(self, v: Optional[Decimal]) -> Optional[str]:
        return serialize_decimal(v)

    @field_serializer("bid_start_time", "original_close_time", "current_close_time", "forced_close_time")
    def serialize_times(self, dt: datetime) -> str:
        return serialize_utc_datetime(dt) or ""

    model_config = ConfigDict(from_attributes=True)


class RFQListResponse(BaseModel):
    items: list[RFQListItem]
    total: int
    page: int
    page_size: int
    server_time: datetime


class SupplierRankDetail(BaseModel):
    rank: Optional[int] = None
    supplier_id: UUID
    supplier_name: str
    carrier_name: Optional[str] = None
    freight_charges: Optional[Decimal] = None
    origin_charges: Optional[Decimal] = None
    destination_charges: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    transit_time_days: Optional[int] = None
    quote_validity_days: Optional[int] = None
    submitted_at: Optional[datetime] = None
    bid_id: Optional[UUID] = None
    no_bid: bool = False

    @field_serializer("freight_charges", "origin_charges", "destination_charges", "total_price")
    def serialize_prices(self, v: Optional[Decimal]) -> Optional[str]:
        return serialize_decimal(v)


class RFQStats(BaseModel):
    total_bids: int
    suppliers_bidding: int
    suppliers_invited: int
    extension_count: int
    first_bid_price: Optional[Decimal] = None
    current_lowest_price: Optional[Decimal] = None
    price_improvement_pct: Optional[Decimal] = None

    @field_serializer("first_bid_price", "current_lowest_price")
    def serialize_prices(self, v: Optional[Decimal]) -> Optional[str]:
        return serialize_decimal(v)

    @field_serializer("price_improvement_pct")
    def serialize_pct(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return str(v.quantize(Decimal("0.01")))


class RFQDetailResponse(BaseModel):
    id: UUID
    reference_id: str
    name: str
    currency: str
    pickup_date: Optional[date] = None
    auction_type: AuctionType
    bid_start_time: datetime
    original_close_time: datetime
    current_close_time: datetime
    forced_close_time: datetime
    status: AuctionStatus
    british_config: Optional[BritishConfigSchema] = None
    invited_suppliers: list[SupplierResponse]
    ranking: list[SupplierRankDetail]
    supplier_rankings: list[SupplierRankDetail] = []
    bid_history: list[BidRecord] = []
    activity_log: list[AuctionEventItem] = []
    in_trigger_window: bool = False
    stats: RFQStats
    created_at: datetime
    server_time: datetime

    @field_serializer("bid_start_time", "original_close_time", "current_close_time", "forced_close_time", "created_at", "server_time")
    def serialize_times(self, dt: datetime) -> str:
        return serialize_utc_datetime(dt) or ""

    model_config = ConfigDict(from_attributes=True)
