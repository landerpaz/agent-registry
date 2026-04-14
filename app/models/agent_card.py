import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AgentCardModel(Base):
    __tablename__ = "agent_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    # Slug derived from name: lowercase, spaces → hyphens. e.g. "Recipe Agent" → "recipe-agent"
    agent_card_id: Mapped[str] = mapped_column(String(255), nullable=False)
    card_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    health_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    health_checked_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("agent_card_id", "version", name="uq_agent_card_id_version"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'not_healthy')", name="ck_agent_cards_status"
        ),
        CheckConstraint(
            "health_status IN ('healthy', 'not_healthy', 'unknown')",
            name="ck_agent_cards_health_status",
        ),
        Index("idx_agent_cards_status", "status", postgresql_where="deleted_at IS NULL"),
        Index("idx_agent_cards_name", "name", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_agent_cards_agent_card_id",
            "agent_card_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_agent_cards_health",
            "health_status",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_agent_cards_created_by",
            "created_by",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_agent_cards_skills",
            "card_data",
            postgresql_using="gin",
            postgresql_ops={"card_data": "jsonb_path_ops"},
        ),
    )


class AgentCardAuditLog(Base):
    __tablename__ = "agent_card_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # UUID FK to agent_cards.id (internal primary key, not the slug column)
    agent_card_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, name="agent_card_id"
    )
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    old_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "operation IN ('created', 'updated', 'deleted')",
            name="ck_audit_log_operation",
        ),
        Index("idx_audit_agent_card", "agent_card_id"),
    )
