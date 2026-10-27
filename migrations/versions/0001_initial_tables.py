"""Create payment storage and reserved idempotency and ledger schemas."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_payments_currency"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=False
        ),
        sa.Column("response_status", sa.SmallInteger(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_idempotency_keys_payment_id", "idempotency_keys", ["payment_id"]
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=False
        ),
        sa.Column("account", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name="ck_ledger_entries_currency"
        ),
        sa.CheckConstraint(
            "direction IN ('debit', 'credit')", name="ck_ledger_direction"
        ),
    )
    op.create_index("ix_ledger_entries_payment_id", "ledger_entries", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_ledger_entries_payment_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_idempotency_keys_payment_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_table("payments")
