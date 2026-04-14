import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._channel = settings.redis_channel

    async def publish(
        self,
        event_type: str,
        agent_id: UUID,
        agent_name: str,
        agent_card_id: str,
        card_data: dict | None = None,
    ) -> None:
        """Fire-and-forget publish to Redis Pub/Sub.

        Exceptions are logged but never propagate to the caller so that a Redis
        outage never fails an otherwise successful API operation.
        """
        payload: dict = {
            "event": event_type,
            "agentId": str(agent_id),
            "agentName": agent_name,
            "agentCardId": agent_card_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        if card_data is not None:
            payload["cardData"] = card_data

        try:
            await self._redis.publish(self._channel, json.dumps(payload))
        except Exception:
            logger.exception(
                "Failed to publish event %s for agent %s", event_type, agent_id
            )
