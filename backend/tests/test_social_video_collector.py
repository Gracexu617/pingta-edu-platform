import pytest

from app.database import create_engine, create_session_factory, initialize_database
from app.services.social_video_collector import SocialVideoAutoCollector


@pytest.mark.asyncio
async def test_social_video_auto_collector_collects_once(test_settings) -> None:
    engine = create_engine(test_settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine, session_factory, auto_create=True)
    collector = SocialVideoAutoCollector(
        session_factory,
        settings=test_settings,
        interval_seconds=60,
    )

    created = await collector.collect_once()
    duplicated = await collector.collect_once()

    await engine.dispose()
    assert created == 0
    assert duplicated == 0


@pytest.mark.asyncio
async def test_social_video_auto_collector_can_stop(test_settings) -> None:
    engine = create_engine(test_settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine, session_factory, auto_create=True)
    collector = SocialVideoAutoCollector(
        session_factory,
        settings=test_settings,
        interval_seconds=60,
    )

    collector.start()
    await collector.stop()

    await engine.dispose()
