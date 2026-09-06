import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_platform_auth_status_hides_secrets(client: AsyncClient) -> None:
    response = await client.get("/api/v1/platform-auth/status")

    assert response.status_code == 200
    data = response.json()
    assert data["providers"][0]["provider"] == "抖音"
    assert "client_secret" not in str(data)
