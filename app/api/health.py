from datetime import datetime, timezone

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.database import get_engine
from app.redis_client import get_redis

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check(response: Response) -> dict:
    db_status = "connected"
    redis_status = "connected"

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    try:
        await get_redis().ping()
    except Exception:
        redis_status = "disconnected"

    is_healthy = db_status == "connected" and redis_status == "connected"
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
