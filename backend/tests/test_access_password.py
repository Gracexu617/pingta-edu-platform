from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.database import initialize_database
from app.main import create_app


@pytest.mark.asyncio
async def test_app_access_password_protects_business_api(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        app_access_password="secret-pass",
        cors_origins=["http://testserver"],
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        database_auto_create=True,
        video_data_provider="disabled",
        tikhub_api_key="",
    )
    app = create_app(settings)
    await initialize_database(app.state.engine, app.state.session_factory, auto_create=True)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        denied = await client.get("/api/v1/sources")
        allowed = await client.get("/api/v1/sources", headers={"X-App-Password": "secret-pass"})
        health = await client.get("/health")

    await app.state.engine.dispose()

    assert denied.status_code == 401
    assert denied.json()["detail"] == "访问密码错误或缺失"
    assert allowed.status_code == 200
    assert health.status_code == 200
