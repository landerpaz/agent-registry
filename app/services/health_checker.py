import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.agent_card import AgentCardModel

logger = logging.getLogger(__name__)

_SEMAPHORE_LIMIT = 50


async def _check_single_agent(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    card_id: str,
    url: str,
    timeout: int,
) -> tuple[str, str]:
    """Returns (card_id, health_status)."""
    async with semaphore:
        for path in ("/health", "/.well-known/agent.json"):
            probe_url = url.rstrip("/") + path
            try:
                resp = await client.get(probe_url, timeout=timeout)
                if resp.status_code == 200:
                    return card_id, "healthy"
            except Exception:
                pass
        return card_id, "not_healthy"


async def check_all_agents_health(
    session_factory: async_sessionmaker[AsyncSession],
    timeout: int,
) -> None:
    logger.info("Starting scheduled health check run")
    async with session_factory() as session:
        result = await session.scalars(
            select(AgentCardModel).where(
                AgentCardModel.deleted_at.is_(None),
                AgentCardModel.status == "active",
            )
        )
        cards = result.all()

    if not cards:
        logger.info("No active agents to health-check")
        return

    semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    checked_at = datetime.now(tz=timezone.utc)

    async with httpx.AsyncClient() as client:
        tasks = []
        for card in cards:
            interfaces = card.card_data.get("supportedInterfaces", [])
            if not interfaces:
                continue
            first_url = interfaces[0].get("url", "")
            if not first_url:
                continue
            tasks.append(
                _check_single_agent(
                    client, semaphore, str(card.id), first_url, timeout
                )
            )

        results: list[tuple[str, str]] = await asyncio.gather(*tasks)

    # Bulk update in a single transaction
    healthy_ids = [cid for cid, status in results if status == "healthy"]
    unhealthy_ids = [cid for cid, status in results if status == "not_healthy"]

    async with session_factory() as session:
        if healthy_ids:
            await session.execute(
                update(AgentCardModel)
                .where(AgentCardModel.id.in_(healthy_ids))
                .values(health_status="healthy", health_checked_at=checked_at)
            )
        if unhealthy_ids:
            await session.execute(
                update(AgentCardModel)
                .where(AgentCardModel.id.in_(unhealthy_ids))
                .values(health_status="not_healthy", health_checked_at=checked_at)
            )
        await session.commit()

    logger.info(
        "Health check complete — healthy: %d, not_healthy: %d",
        len(healthy_ids),
        len(unhealthy_ids),
    )
