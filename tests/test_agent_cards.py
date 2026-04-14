import copy
import pytest
from httpx import AsyncClient

from tests.conftest import SAMPLE_CARD
from app.services.agent_card_service import slugify


# ---------------------------------------------------------------------------
# Unit tests — slugify helper
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert slugify("Recipe Agent") == "recipe-agent"


def test_slugify_extra_spaces():
    assert slugify("My  Cool Agent") == "my-cool-agent"


def test_slugify_leading_trailing():
    assert slugify("  Agent  ") == "agent"


def test_slugify_already_lower():
    assert slugify("simple") == "simple"


# ---------------------------------------------------------------------------
# API integration tests (require a running test DB; skip otherwise)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio


async def test_create_agent_card(client: AsyncClient):
    resp = await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["operationStatus"] == "success"
    assert body["agentCardId"] == "test-agent"
    assert body["agentName"] == "Test Agent"


async def test_create_duplicate_fails(client: AsyncClient):
    await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    resp = await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    body = resp.json()
    assert body["operationStatus"] == "failed"
    assert "already exists" in body["errorDetail"]


async def test_create_different_version_succeeds(client: AsyncClient):
    card_v2 = copy.deepcopy(SAMPLE_CARD)
    card_v2["version"] = "2.0.0"
    resp = await client.post("/api/v1/agent-cards", json=card_v2)
    assert resp.status_code == 201
    assert resp.json()["operationStatus"] == "success"


async def test_list_returns_latest_version(client: AsyncClient):
    # Create v1 and v2 of the same agent
    await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    card_v2 = copy.deepcopy(SAMPLE_CARD)
    card_v2["version"] = "2.0.0"
    await client.post("/api/v1/agent-cards", json=card_v2)

    resp = await client.get("/api/v1/agent-cards")
    assert resp.status_code == 200
    body = resp.json()
    # Only one entry per agent slug
    slugs = [item["agentCardId"] for item in body["items"]]
    assert slugs.count("test-agent") == 1
    # That entry should be the latest version
    test_agent = next(i for i in body["items"] if i["agentCardId"] == "test-agent")
    assert test_agent["cardData"]["version"] == "2.0.0"


async def test_get_by_id(client: AsyncClient):
    create_resp = await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    agent_id = create_resp.json()["agentId"]

    resp = await client.get(f"/api/v1/agent-cards/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


async def test_get_by_id_not_found(client: AsyncClient):
    import uuid
    resp = await client.get(f"/api/v1/agent-cards/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_by_slug_latest(client: AsyncClient):
    await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    card_v2 = copy.deepcopy(SAMPLE_CARD)
    card_v2["version"] = "3.0.0"
    await client.post("/api/v1/agent-cards", json=card_v2)

    resp = await client.get("/api/v1/agent-cards/by-slug/test-agent")
    assert resp.status_code == 200
    assert resp.json()["cardData"]["version"] == "3.0.0"


async def test_get_all_versions_by_slug(client: AsyncClient):
    await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    card_v2 = copy.deepcopy(SAMPLE_CARD)
    card_v2["version"] = "2.0.0"
    await client.post("/api/v1/agent-cards", json=card_v2)

    resp = await client.get("/api/v1/agent-cards/by-slug/test-agent/versions")
    assert resp.status_code == 200
    versions = [c["cardData"]["version"] for c in resp.json()]
    assert "1.0.0" in versions
    assert "2.0.0" in versions


async def test_search_by_name(client: AsyncClient):
    await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    resp = await client.get("/api/v1/agent-cards/search?name=Test Agent")
    assert resp.status_code == 200
    assert resp.json()["agentCardId"] == "test-agent"


async def test_search_by_name_and_version(client: AsyncClient):
    await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    card_v2 = copy.deepcopy(SAMPLE_CARD)
    card_v2["version"] = "2.0.0"
    await client.post("/api/v1/agent-cards", json=card_v2)

    resp = await client.get(
        "/api/v1/agent-cards/search?name=Test Agent&version=1.0.0"
    )
    assert resp.status_code == 200
    assert resp.json()["cardData"]["version"] == "1.0.0"


async def test_search_missing_name(client: AsyncClient):
    resp = await client.get("/api/v1/agent-cards/search")
    assert resp.status_code == 400


async def test_update_agent_card(client: AsyncClient):
    create_resp = await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    agent_id = create_resp.json()["agentId"]

    updated = copy.deepcopy(SAMPLE_CARD)
    updated["description"] = "Updated description"
    resp = await client.put(f"/api/v1/agent-cards/{agent_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["operationStatus"] == "success"


async def test_delete_agent_card(client: AsyncClient):
    create_resp = await client.post("/api/v1/agent-cards", json=SAMPLE_CARD)
    agent_id = create_resp.json()["agentId"]

    resp = await client.delete(f"/api/v1/agent-cards/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["operationStatus"] == "success"

    # Should 404 now
    resp = await client.get(f"/api/v1/agent-cards/{agent_id}")
    assert resp.status_code == 404


async def test_delete_not_found(client: AsyncClient):
    import uuid
    resp = await client.delete(f"/api/v1/agent-cards/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_pagination(client: AsyncClient):
    resp = await client.get("/api/v1/agent-cards?page=1&pageSize=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "totalPages" in body
