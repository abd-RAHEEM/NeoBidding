from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


def serialize_decimal(v: Optional[Decimal]) -> Optional[str]:
    if v is None:
        return None
    return str(Decimal(str(v)).quantize(Decimal("0.01")))


def serialize_utc_datetime(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BidCreate(BaseModel):
    supplier_id: UUID
    freight_charges: Decimal = Field(..., ge=0, description="Freight charges (non-negative, 2 decimals max)")
    origin_charges: Decimal = Field(..., ge=0, description="Origin charges (non-negative, 2 decimals max)")
    destination_charges: Decimal = Field(..., ge=0, description="Destination charges (non-negative, 2 decimals max)")
    transit_time_days: int = Field(..., ge=1, description="Estimated transit time in days")
    quote_validity_days: int = Field(..., ge=1, description="Quote validity period in days")

    @model_validator(mode="after")
    def validate_total_positive_and_precision(self) -> "BidCreate":
        total = self.freight_charges + self.origin_charges + self.destination_charges
        if total <= Decimal("0.00"):
            raise ValueError("Total quote price must be greater than zero.")
        # Ensure max 2 decimal places
        for field_name in ["freight_charges", "origin_charges", "destination_charges"]:
            val: Decimal = getattr(self, field_name)
            if val.as_tuple().exponent < -2:
                raise ValueError(f"{field_name} must have at most 2 decimal places.")
        return self


class BidRecord(BaseModel):
    id: UUID
    rfq_id: UUID
    supplier_id: UUID
    carrier_name: str
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total_price: Decimal
    transit_time_days: int
    quote_validity_days: int
    submitted_at: datetime

    @field_serializer("freight_charges", "origin_charges", "destination_charges", "total_price")
    def serialize_prices(self, v: Decimal) -> str:
        return serialize_decimal(v) or "0.00"

    @field_serializer("submitted_at")
    def serialize_submitted_at(self, dt: datetime) -> str:
        return serialize_utc_datetime(dt) or ""

    model_config = ConfigDict(from_attributes=True)


class BidSubmissionResult(BaseModel):
    bid: BidRecord
    rank: int
    extended: bool
    new_close_time: datetime
    extension_reason: Optional[str] = None
    server_time: datetime

    @field_serializer("new_close_time", "server_time")
    def serialize_timestamps(self, dt: datetime) -> str:
        return serialize_utc_datetime(dt) or ""


class BidHistoryListResponse(BaseModel):
    items: list[BidRecord]
    total: int
    page: int
    page_size: int
    server_time: datetime

    @field_serializer("server_time")
    def serialize_server_time(self, dt: datetime) -> str:
        return serialize_utc_datetime(dt) or ""
