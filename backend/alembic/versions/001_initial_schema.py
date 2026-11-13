"""Initial schema with all tables, constraints, enums and indexes

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Suppliers
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    # 2. RFQs
    op.create_table(
        "rfqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("reference_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="INR"),
        sa.Column("pickup_date", sa.Date(), nullable=True),
        sa.Column(
            "auction_type",
            sa.Enum("STANDARD", "BRITISH", name="auction_type_enum"),
            nullable=False,
            server_default="STANDARD",
        ),
        sa.Column("bid_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forced_close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("SCHEDULED", "ACTIVE", "CLOSED", "FORCE_CLOSED", name="auction_status_enum"),
            nullable=False,
            server_default="SCHEDULED",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("forced_close_time > original_close_time", name="chk_forced_after_original"),
        sa.CheckConstraint("original_close_time > bid_start_time", name="chk_original_after_start"),
        sa.CheckConstraint(
            "current_close_time >= original_close_time AND current_close_time <= forced_close_time",
            name="chk_current_in_bounds",
        ),
        sa.CheckConstraint("currency IN ('INR','USD','EUR','GBP','AED')", name="chk_currency_valid"),
    )
    op.create_index("ix_rfqs_reference_id", "rfqs", ["reference_id"])
    op.create_index("idx_rfqs_status_close", "rfqs", ["status", "current_close_time"])

    # 3. RFQ Suppliers
    op.create_table(
        "rfq_suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rfq_id", "supplier_id", name="uq_rfq_supplier"),
    )

    # 4. British Auction Configs
    op.create_table(
        "british_auction_configs",
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trigger_window_minutes", sa.Integer(), nullable=False),
        sa.Column("extension_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "extension_trigger",
            sa.Enum("BID_IN_LAST_X", "ANY_RANK_CHANGE_IN_LAST_X", "L1_CHANGE_IN_LAST_X", name="extension_trigger_enum"),
            nullable=False,
        ),
        sa.CheckConstraint("trigger_window_minutes >= 1", name="chk_trigger_window_positive"),
        sa.CheckConstraint("extension_minutes >= 1", name="chk_extension_positive"),
    )

    # 5. Bids
    op.create_table(
        "bids",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("carrier_name", sa.String(length=255), nullable=False),
        sa.Column("freight_charges", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("origin_charges", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("destination_charges", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("transit_time_days", sa.Integer(), nullable=False),
        sa.Column("quote_validity_days", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("request_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("freight_charges >= 0", name="chk_freight_nonneg"),
        sa.CheckConstraint("origin_charges >= 0", name="chk_origin_nonneg"),
        sa.CheckConstraint("destination_charges >= 0", name="chk_destination_nonneg"),
        sa.CheckConstraint("total_price > 0", name="chk_total_positive"),
        sa.CheckConstraint(
            "total_price = freight_charges + origin_charges + destination_charges",
            name="chk_total_sum",
        ),
        sa.CheckConstraint("transit_time_days >= 1", name="chk_transit_positive"),
        sa.CheckConstraint("quote_validity_days >= 1", name="chk_validity_positive"),
        sa.UniqueConstraint("rfq_id", "supplier_id", "idempotency_key", name="uq_bid_idempotency"),
    )
    op.create_index("idx_bids_rfq_supplier_total", "bids", ["rfq_id", "supplier_id", "total_price"])
    op.create_index("idx_bids_rfq_total_time", "bids", ["rfq_id", "total_price", "submitted_at"])

    # 6. Auction Events
    op.create_table(
        "auction_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "AUCTION_CREATED",
                "AUCTION_STARTED",
                "BID_PLACED",
                "TIME_EXTENDED",
                "EXTENSION_SKIPPED_AT_FORCED_CLOSE",
                "AUCTION_CLOSED",
                "AUCTION_FORCE_CLOSED",
                name="auction_event_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("bid_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bids.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_recovered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("idx_events_rfq_occurred", "auction_events", ["rfq_id", "occurred_at", "id"])

    # Partial unique index for lifecycle recovery idempotency
    op.execute(
        """
        CREATE UNIQUE INDEX uix_lifecycle_events ON auction_events (rfq_id, event_type)
        WHERE event_type IN ('AUCTION_STARTED', 'AUCTION_CLOSED', 'AUCTION_FORCE_CLOSED');
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uix_lifecycle_events;")
    op.drop_table("auction_events")
    op.drop_table("bids")
    op.drop_table("british_auction_configs")
    op.drop_table("rfq_suppliers")
    op.drop_table("rfqs")
    op.drop_table("suppliers")
    op.execute("DROP TYPE IF EXISTS auction_event_type_enum;")
    op.execute("DROP TYPE IF EXISTS extension_trigger_enum;")
    op.execute("DROP TYPE IF EXISTS auction_status_enum;")
    op.execute("DROP TYPE IF EXISTS auction_type_enum;")
