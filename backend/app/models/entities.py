import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.types import TypeDecorator, CHAR, JSON
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.enums import (
    AuctionEventType,
    AuctionStatus,
    AuctionType,
    ExtensionTrigger,
)


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


# JSON/JSONB dialect-adaptive type
JSONType = JSONB().with_variant(JSON(), "sqlite")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    invitations = relationship("RFQSupplier", back_populates="supplier", passive_deletes=True)
    bids = relationship("Bid", back_populates="supplier", passive_deletes=True)


class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    reference_id = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    currency = Column(CHAR(3), nullable=False, default="INR")
    pickup_date = Column(Date, nullable=True)
    auction_type = Column(SAEnum(AuctionType, name="auction_type_enum"), nullable=False, default=AuctionType.STANDARD)
    bid_start_time = Column(DateTime(timezone=True), nullable=False)
    original_close_time = Column(DateTime(timezone=True), nullable=False)
    current_close_time = Column(DateTime(timezone=True), nullable=False)
    forced_close_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(SAEnum(AuctionStatus, name="auction_status_enum"), nullable=False, default=AuctionStatus.SCHEDULED)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("forced_close_time > original_close_time", name="chk_forced_after_original"),
        CheckConstraint("original_close_time > bid_start_time", name="chk_original_after_start"),
        CheckConstraint(
            "current_close_time >= original_close_time AND current_close_time <= forced_close_time",
            name="chk_current_in_bounds",
        ),
        CheckConstraint("currency IN ('INR','USD','EUR','GBP','AED')", name="chk_currency_valid"),
        Index("idx_rfqs_status_close", "status", "current_close_time"),
    )

    # Relationships
    invited_suppliers = relationship("RFQSupplier", back_populates="rfq", cascade="all, delete-orphan")
    british_config = relationship("BritishAuctionConfig", back_populates="rfq", uselist=False, cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="rfq")
    events = relationship("AuctionEvent", back_populates="rfq")


class RFQSupplier(Base):
    __tablename__ = "rfq_suppliers"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    rfq_id = Column(GUID, ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(GUID, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    invited_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_rfq_supplier"),
    )

    # Relationships
    rfq = relationship("RFQ", back_populates="invited_suppliers")
    supplier = relationship("Supplier", back_populates="invitations")


class BritishAuctionConfig(Base):
    __tablename__ = "british_auction_configs"

    rfq_id = Column(GUID, ForeignKey("rfqs.id", ondelete="CASCADE"), primary_key=True)
    trigger_window_minutes = Column(Integer, nullable=False)
    extension_minutes = Column(Integer, nullable=False)
    extension_trigger = Column(SAEnum(ExtensionTrigger, name="extension_trigger_enum"), nullable=False)

    __table_args__ = (
        CheckConstraint("trigger_window_minutes >= 1", name="chk_trigger_window_positive"),
        CheckConstraint("extension_minutes >= 1", name="chk_extension_positive"),
    )

    # Relationships
    rfq = relationship("RFQ", back_populates="british_config")


class Bid(Base):
    __tablename__ = "bids"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    rfq_id = Column(GUID, ForeignKey("rfqs.id", ondelete="RESTRICT"), nullable=False)
    supplier_id = Column(GUID, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    carrier_name = Column(String(255), nullable=False)
    freight_charges = Column(Numeric(14, 2), nullable=False)
    origin_charges = Column(Numeric(14, 2), nullable=False)
    destination_charges = Column(Numeric(14, 2), nullable=False)
    total_price = Column(Numeric(14, 2), nullable=False)
    transit_time_days = Column(Integer, nullable=False)
    quote_validity_days = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)  # Explicitly application-managed
    idempotency_key = Column(String(64), nullable=True)
    request_hash = Column(CHAR(64), nullable=True)
    result_snapshot = Column(JSONType, nullable=True)

    __table_args__ = (
        CheckConstraint("freight_charges >= 0", name="chk_freight_nonneg"),
        CheckConstraint("origin_charges >= 0", name="chk_origin_nonneg"),
        CheckConstraint("destination_charges >= 0", name="chk_destination_nonneg"),
        CheckConstraint("total_price > 0", name="chk_total_positive"),
        CheckConstraint(
            "total_price = freight_charges + origin_charges + destination_charges",
            name="chk_total_sum",
        ),
        CheckConstraint("transit_time_days >= 1", name="chk_transit_positive"),
        CheckConstraint("quote_validity_days >= 1", name="chk_validity_positive"),
        UniqueConstraint("rfq_id", "supplier_id", "idempotency_key", name="uq_bid_idempotency"),
        Index("idx_bids_rfq_supplier_total", "rfq_id", "supplier_id", "total_price"),
        Index("idx_bids_rfq_total_time", "rfq_id", "total_price", "submitted_at"),
    )

    # Relationships
    rfq = relationship("RFQ", back_populates="bids")
    supplier = relationship("Supplier", back_populates="bids")


class AuctionEvent(Base):
    __tablename__ = "auction_events"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    rfq_id = Column(GUID, ForeignKey("rfqs.id", ondelete="RESTRICT"), nullable=False)
    event_type = Column(SAEnum(AuctionEventType, name="auction_event_type_enum"), nullable=False)
    bid_id = Column(GUID, ForeignKey("bids.id", ondelete="RESTRICT"), nullable=True)
    payload = Column(JSONType, nullable=False, default=dict)
    reason = Column(Text, nullable=False, default="")
    occurred_at = Column(DateTime(timezone=True), nullable=False)  # Explicitly application-managed
    created_at = Column(DateTime(timezone=True), nullable=False)   # Explicitly application-managed
    is_recovered = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_events_rfq_occurred", "rfq_id", "occurred_at", "id"),
    )

    # Relationships
    rfq = relationship("RFQ", back_populates="events")
    bid = relationship("Bid")

