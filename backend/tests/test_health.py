import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_service_status(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json() == {
        "status": "ok",
        "service": "AI Education Intelligence API",
        "version": "0.1.0",
        "environment": "test",
        "request_id": "test-request",
    }
