from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Supplier / Carrier company name")


class SupplierCreate(SupplierBase):
    pass


class SupplierResponse(SupplierBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
    page: int
    page_size: int

