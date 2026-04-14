from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.okta import get_current_user, get_optional_user
from app.database import get_session
from app.events.publisher import EventPublisher
from app.redis_client import get_redis

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DBSession = Annotated[AsyncSession, Depends(get_session)]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
OptionalUser = Annotated[dict[str, Any] | None, Depends(get_optional_user)]

# ---------------------------------------------------------------------------
# Event publisher
# ---------------------------------------------------------------------------


def get_publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


Publisher = Annotated[EventPublisher, Depends(get_publisher)]
