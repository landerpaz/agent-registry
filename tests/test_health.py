import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)  # depends on whether test DB/Redis are up
    body = resp.json()
    assert "status" in body
    assert "database" in body
    assert "redis" in body
    assert "timestamp" in body
