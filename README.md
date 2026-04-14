# A2A Agent Registry

A production-ready centralised registry for A2A-compliant agents. Agents publish their Agent Cards here for discovery. Built with FastAPI, PostgreSQL (asyncpg), Redis Pub/Sub, and Okta JWT auth.

---

## Quick Start

### 1. Copy and configure environment

```bash
cp .env.example .env
# Edit .env — set OKTA_* values or set OKTA_VALIDATION_ENABLED=false for local dev
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 3. Run locally (without Docker)

```bash
# Start dependencies
docker compose up db redis -d

# Install deps
pip install -r requirements-dev.txt

# Apply migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

---

## Configuration

All settings are loaded from environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_CHANNEL` | `agent_registry_events` | Pub/Sub channel name |
| `OKTA_VALIDATION_ENABLED` | `true` | Set `false` to open all APIs (dev only) |
| `OKTA_ISSUER` | — | Okta issuer URL |
| `OKTA_AUDIENCE` | — | Okta audience string |
| `OKTA_JWKS_URI` | — | Okta JWKS endpoint |
| `HEALTH_CHECK_INTERVAL_SECONDS` | `3600` | Agent health check frequency |
| `HEALTH_CHECK_TIMEOUT_SECONDS` | `10` | Per-agent HTTP timeout |
| `DEFAULT_PAGE_SIZE` | `20` | Default pagination size |
| `MAX_PAGE_SIZE` | `100` | Maximum pagination size |

---

## API Reference

All write endpoints require `Authorization: Bearer <token>` unless `OKTA_VALIDATION_ENABLED=false`.

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service health (DB + Redis) |

### Agent Cards

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/agent-cards` | Required | Register a new agent card |
| PUT | `/api/v1/agent-cards/{id}` | Required (owner) | Replace an agent card |
| DELETE | `/api/v1/agent-cards/{id}` | Required (owner) | Soft-delete an agent card |
| GET | `/api/v1/agent-cards` | Optional | List agents (latest version per agent) |
| GET | `/api/v1/agent-cards/{id}` | Optional | Get agent card by internal UUID |
| GET | `/api/v1/agent-cards/by-slug/{agent_card_id}` | Optional | Get latest version by slug |
| GET | `/api/v1/agent-cards/by-slug/{agent_card_id}/versions` | Optional | List all versions of an agent |
| GET | `/api/v1/agent-cards/search?name=X` | Optional | Search by name (returns latest version) |
| GET | `/api/v1/agent-cards/search?name=X&version=Y` | Optional | Search by name + exact version |

### Slug generation

The `agentCardId` slug is derived from the agent `name` at creation time:
- Lowercase
- Whitespace sequences replaced with `-`
- Example: `"Recipe Agent"` → `"recipe-agent"`

The slug never changes after creation (renaming via PUT does not update the slug).

### Versioning

Multiple versions of the same agent can coexist (`"recipe-agent"` v1.0.0 and v2.0.0 are independent rows). List and search endpoints return only the **latest version** per agent unless the `/versions` sub-resource or an explicit `version` query param is used.

### Events (Redis Pub/Sub)

Published on channel `agent_registry_events`:

```json
{
  "event": "agent_card_created | agent_card_updated | agent_card_deleted",
  "agentId": "<uuid>",
  "agentName": "Recipe Agent",
  "agentCardId": "recipe-agent",
  "timestamp": "2026-04-13T00:00:00+00:00",
  "cardData": { ... }
}
```

`cardData` is omitted for `agent_card_deleted` events.

---

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## Running Tests

```bash
# Requires a running PostgreSQL on localhost:5432 with database agent_registry_test
pip install -r requirements-dev.txt
pytest --cov=app --cov-report=term-missing
```

---

## Project Structure

```
app/
├── main.py                  # FastAPI app, lifespan, middleware
├── config.py                # Settings (pydantic-settings)
├── database.py              # Async SQLAlchemy engine + session factory
├── redis_client.py          # Redis connection pool
├── models/agent_card.py     # SQLAlchemy ORM models
├── schemas/agent_card.py    # Pydantic request/response models (camelCase)
├── schemas/common.py        # PaginatedResponse
├── api/
│   ├── deps.py              # FastAPI dependency injection
│   ├── health.py            # GET /health
│   └── agent_cards.py       # CRUD endpoints
├── auth/okta.py             # Okta JWT validation
├── services/
│   ├── agent_card_service.py  # Business logic + slugify
│   └── health_checker.py      # Scheduled health checks
└── events/publisher.py      # Redis Pub/Sub publisher
alembic/                     # Database migrations
tests/                       # pytest integration tests
```
