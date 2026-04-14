import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_card import AgentCardAuditLog, AgentCardModel
from app.schemas.agent_card import AgentCardCreate, AgentCardResponse, OperationResponse
from app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Derive a stable slug from an agent name.

    "Recipe Agent"   → "recipe-agent"
    "My  Cool Agent" → "my-cool-agent"
    """
    return re.sub(r"\s+", "-", name.strip()).lower()


def _model_to_response(card: AgentCardModel) -> AgentCardResponse:
    return AgentCardResponse(
        id=card.id,
        agentCardId=card.agent_card_id,
        cardData=card.card_data,
        status=card.status,
        healthStatus=card.health_status,
        healthCheckedAt=card.health_checked_at,
        createdBy=card.created_by,
        updatedBy=card.updated_by,
        createdAt=card.created_at,
        updatedAt=card.updated_at,
    )


def _card_to_dict(payload: AgentCardCreate) -> dict:
    """Serialise the Pydantic request model to a camelCase dict for JSONB storage."""
    return payload.model_dump(by_alias=True, exclude_none=True)


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

async def create_agent_card(
    session: AsyncSession,
    payload: AgentCardCreate,
    current_user: dict[str, Any],
) -> OperationResponse:
    slug = slugify(payload.name)

    # Check uniqueness — applies even to soft-deleted rows
    existing = await session.scalar(
        select(AgentCardModel).where(
            AgentCardModel.agent_card_id == slug,
            AgentCardModel.version == payload.version,
        )
    )
    if existing is not None:
        return OperationResponse(
            agentId=existing.id,
            agentName=existing.name,
            agentCardId=slug,
            operationStatus="failed",
            errorDetail=(
                f"Agent '{payload.name}' version '{payload.version}' already exists"
            ),
        )

    card_data = _card_to_dict(payload)
    card = AgentCardModel(
        id=uuid.uuid4(),
        name=payload.name,
        version=payload.version,
        agent_card_id=slug,
        card_data=card_data,
        status="active",
        health_status="unknown",
        created_by=current_user["sub"],
    )
    session.add(card)

    audit = AgentCardAuditLog(
        agent_card_ref_id=card.id,
        operation="created",
        performed_by=current_user["sub"],
        old_data=None,
        new_data=card_data,
    )
    session.add(audit)

    await session.commit()
    await session.refresh(card)

    logger.info("Created agent card %s (%s)", card.agent_card_id, card.id)
    return OperationResponse(
        agentId=card.id,
        agentName=card.name,
        agentCardId=card.agent_card_id,
        operationStatus="success",
    )


async def update_agent_card(
    session: AsyncSession,
    internal_id: uuid.UUID,
    payload: AgentCardCreate,
    current_user: dict[str, Any],
) -> OperationResponse:
    card = await session.scalar(
        select(AgentCardModel).where(
            AgentCardModel.id == internal_id,
            AgentCardModel.deleted_at.is_(None),
        )
    )
    if card is None:
        return OperationResponse(
            agentId=internal_id,
            agentName=None,
            agentCardId=None,
            operationStatus="failed",
            errorDetail="Agent card not found",
        )

    if card.created_by != current_user["sub"]:
        return OperationResponse(
            agentId=card.id,
            agentName=card.name,
            agentCardId=card.agent_card_id,
            operationStatus="failed",
            errorDetail="Forbidden: you are not the owner of this agent card",
        )

    old_data = card.card_data
    new_data = _card_to_dict(payload)

    card.name = payload.name
    card.version = payload.version
    card.card_data = new_data
    card.updated_by = current_user["sub"]
    card.updated_at = datetime.now(tz=timezone.utc)

    audit = AgentCardAuditLog(
        agent_card_ref_id=card.id,
        operation="updated",
        performed_by=current_user["sub"],
        old_data=old_data,
        new_data=new_data,
    )
    session.add(audit)

    await session.commit()
    await session.refresh(card)

    logger.info("Updated agent card %s (%s)", card.agent_card_id, card.id)
    return OperationResponse(
        agentId=card.id,
        agentName=card.name,
        agentCardId=card.agent_card_id,
        operationStatus="success",
    )


async def delete_agent_card(
    session: AsyncSession,
    internal_id: uuid.UUID,
    current_user: dict[str, Any],
) -> OperationResponse:
    card = await session.scalar(
        select(AgentCardModel).where(
            AgentCardModel.id == internal_id,
            AgentCardModel.deleted_at.is_(None),
        )
    )
    if card is None:
        return OperationResponse(
            agentId=internal_id,
            agentName=None,
            agentCardId=None,
            operationStatus="failed",
            errorDetail="Agent card not found",
        )

    if card.created_by != current_user["sub"]:
        return OperationResponse(
            agentId=card.id,
            agentName=card.name,
            agentCardId=card.agent_card_id,
            operationStatus="failed",
            errorDetail="Forbidden: you are not the owner of this agent card",
        )

    card.deleted_at = datetime.now(tz=timezone.utc)
    card.status = "inactive"
    card.updated_by = current_user["sub"]

    audit = AgentCardAuditLog(
        agent_card_ref_id=card.id,
        operation="deleted",
        performed_by=current_user["sub"],
        old_data=card.card_data,
        new_data=None,
    )
    session.add(audit)

    await session.commit()

    logger.info("Deleted agent card %s (%s)", card.agent_card_id, card.id)
    return OperationResponse(
        agentId=card.id,
        agentName=card.name,
        agentCardId=card.agent_card_id,
        operationStatus="success",
    )


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

async def get_agent_card_by_id(
    session: AsyncSession, internal_id: uuid.UUID
) -> AgentCardResponse | None:
    card = await session.scalar(
        select(AgentCardModel).where(
            AgentCardModel.id == internal_id,
            AgentCardModel.deleted_at.is_(None),
        )
    )
    return _model_to_response(card) if card else None


async def list_agent_cards(
    session: AsyncSession,
    page: int,
    page_size: int,
    status_filter: str | None = None,
) -> PaginatedResponse[AgentCardResponse]:
    """Return the latest version per agent_card_id, paginated."""
    where_clauses = "WHERE deleted_at IS NULL"
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}

    if status_filter:
        where_clauses += " AND status = :status"
        params["status"] = status_filter

    # DISTINCT ON ensures only the latest version per slug is returned.
    # Version ordering is lexicographic — sufficient for semver strings
    # stored with consistent zero-padding (e.g. "1.0.0", "2.0.0").
    rows = await session.execute(
        text(
            f"""
            SELECT *
            FROM (
                SELECT DISTINCT ON (agent_card_id) *
                FROM agent_cards
                {where_clauses}
                ORDER BY agent_card_id, version DESC
            ) latest
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total: int = await session.scalar(
        text(
            f"""
            SELECT COUNT(DISTINCT agent_card_id)
            FROM agent_cards
            {where_clauses}
            """
        ),
        count_params,
    )

    cards = [AgentCardResponse(
        id=row.id,
        agentCardId=row.agent_card_id,
        cardData=row.card_data,
        status=row.status,
        healthStatus=row.health_status,
        healthCheckedAt=row.health_checked_at,
        createdBy=row.created_by,
        updatedBy=row.updated_by,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    ) for row in rows]

    return PaginatedResponse(
        items=cards,
        total=total or 0,
        page=page,
        pageSize=page_size,
        totalPages=math.ceil((total or 0) / page_size) if page_size else 0,
    )


async def get_latest_by_slug(
    session: AsyncSession, slug: str
) -> AgentCardResponse | None:
    card = await session.scalar(
        select(AgentCardModel)
        .where(
            AgentCardModel.agent_card_id == slug,
            AgentCardModel.deleted_at.is_(None),
        )
        .order_by(AgentCardModel.version.desc())
        .limit(1)
    )
    return _model_to_response(card) if card else None


async def get_all_versions_by_slug(
    session: AsyncSession, slug: str
) -> list[AgentCardResponse]:
    result = await session.scalars(
        select(AgentCardModel)
        .where(
            AgentCardModel.agent_card_id == slug,
            AgentCardModel.deleted_at.is_(None),
        )
        .order_by(AgentCardModel.version.desc())
    )
    return [_model_to_response(c) for c in result.all()]


async def search_agent_cards(
    session: AsyncSession, name: str, version: str | None = None
) -> AgentCardResponse | None:
    """Search by name (exact, case-insensitive via slug) and optionally version."""
    slug = slugify(name)

    if version:
        card = await session.scalar(
            select(AgentCardModel).where(
                AgentCardModel.agent_card_id == slug,
                AgentCardModel.version == version,
                AgentCardModel.deleted_at.is_(None),
            )
        )
        return _model_to_response(card) if card else None

    return await get_latest_by_slug(session, slug)
