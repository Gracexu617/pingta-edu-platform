from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.database import initialize_database
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        cors_origins=["http://testserver"],
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        database_auto_create=True,
        video_data_provider="disabled",
        tikhub_api_key="",
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncClient:
    app = create_app(test_settings)
    await initialize_database(
        app.state.engine,
        app.state.session_factory,
        auto_create=test_settings.database_auto_create,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await app.state.engine.dispose()
