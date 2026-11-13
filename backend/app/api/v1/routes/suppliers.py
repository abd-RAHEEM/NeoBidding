from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_db
from app.models.entities import Supplier
from app.schemas.supplier import SupplierCreate, SupplierListResponse, SupplierResponse
from app.services.clock import Clock

router = APIRouter()


@router.get("/suppliers", response_model=SupplierListResponse, tags=["Suppliers"])
def list_suppliers(
    q: Optional[str] = Query(None, description="Search suppliers by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = select(Supplier)
    if q:
        query = query.where(Supplier.name.ilike(f"%{q.strip()}%"))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(
        query.order_by(Supplier.name.asc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED, tags=["Suppliers"])
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
):
    now = clock.now()
    existing = db.execute(select(Supplier).where(Supplier.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SUPPLIER_NAME_CONFLICT",
                "message": f"Supplier with name '{payload.name}' already exists.",
                "details": {"name": payload.name},
            },
        )

    supplier = Supplier(name=payload.name, created_at=now)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)
