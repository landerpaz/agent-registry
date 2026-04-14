import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.agent_cards import router as agent_cards_router
from app.api.health import router as health_router
from app.config import settings
from app.database import close_db, get_session_factory, init_db
from app.events.publisher import EventPublisher
from app.redis_client import close_redis, get_redis, init_redis
from app.services.health_checker import check_all_agents_health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    await init_db()
    await init_redis()

    app.state.publisher = EventPublisher(get_redis())

    _scheduler.add_job(
        check_all_agents_health,
        trigger="interval",
        seconds=settings.health_check_interval_seconds,
        kwargs={
            "session_factory": get_session_factory(),
            "timeout": settings.health_check_timeout_seconds,
        },
        id="health_checker",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Agent Registry started")

    yield

    # ---- Shutdown ----
    _scheduler.shutdown(wait=False)
    await close_redis()
    await close_db()
    logger.info("Agent Registry stopped")


app = FastAPI(
    title="A2A Agent Registry",
    version="1.0.0",
    description="Centralised registry for A2A-compliant agents.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception for %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(agent_cards_router, prefix="/api/v1")
