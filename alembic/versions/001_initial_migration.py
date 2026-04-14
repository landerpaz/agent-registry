"""Initial migration — agent_cards and agent_card_audit_log tables

Revision ID: 001
Revises:
Create Date: 2026-04-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("agent_card_id", sa.String(255), nullable=False),
        sa.Column("card_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "health_status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("agent_card_id", "version", name="uq_agent_card_id_version"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'not_healthy')",
            name="ck_agent_cards_status",
        ),
        sa.CheckConstraint(
            "health_status IN ('healthy', 'not_healthy', 'unknown')",
            name="ck_agent_cards_health_status",
        ),
    )

    # Partial indexes (WHERE deleted_at IS NULL)
    op.create_index(
        "idx_agent_cards_status",
        "agent_cards",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_agent_cards_name",
        "agent_cards",
        ["name"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_agent_cards_agent_card_id",
        "agent_cards",
        ["agent_card_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_agent_cards_health",
        "agent_cards",
        ["health_status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_agent_cards_created_by",
        "agent_cards",
        ["created_by"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # GIN index for JSONB skill/tag queries
    op.create_index(
        "idx_agent_cards_card_data",
        "agent_cards",
        ["card_data"],
        postgresql_using="gin",
    )

    # Audit log table
    op.create_table(
        "agent_card_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("performed_by", sa.String(255), nullable=False),
        sa.Column("old_data", postgresql.JSONB(), nullable=True),
        sa.Column("new_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('created', 'updated', 'deleted')",
            name="ck_audit_log_operation",
        ),
    )
    op.create_index(
        "idx_audit_agent_card",
        "agent_card_audit_log",
        ["agent_card_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_agent_card", table_name="agent_card_audit_log")
    op.drop_table("agent_card_audit_log")

    op.drop_index("idx_agent_cards_card_data", table_name="agent_cards")
    op.drop_index("idx_agent_cards_created_by", table_name="agent_cards")
    op.drop_index("idx_agent_cards_health", table_name="agent_cards")
    op.drop_index("idx_agent_cards_agent_card_id", table_name="agent_cards")
    op.drop_index("idx_agent_cards_name", table_name="agent_cards")
    op.drop_index("idx_agent_cards_status", table_name="agent_cards")
    op.drop_table("agent_cards")
