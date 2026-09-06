from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.changzhou_news import router as changzhou_news_router
from app.api.routes.collect_tasks import router as collect_tasks_router
from app.api.routes.health import router as health_router
from app.api.routes.influencers import router as influencers_router
from app.api.routes.materials import router as materials_router
from app.api.routes.platform_auth import router as platform_auth_router
from app.api.routes.search import router as search_router
from app.api.routes.social_creators import router as social_creators_router
from app.api.routes.social_videos import router as social_videos_router
from app.api.routes.sources import router as sources_router
from app.api.routes.wechat import router as wechat_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import AccessPasswordMiddleware, RequestIdMiddleware
from app.database import create_engine, create_session_factory, initialize_database
from app.services.changzhou_news_collector import ChangzhouNewsAutoCollector
from app.services.social_video_collector import SocialVideoAutoCollector


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    configure_logging(settings.log_level)
    await initialize_database(
        app.state.engine,
        app.state.session_factory,
        auto_create=settings.database_auto_create,
    )
    collector: SocialVideoAutoCollector | None = None
    news_collector: ChangzhouNewsAutoCollector | None = None
    if settings.environment != "test" and settings.social_video_auto_collect_enabled:
        collector = SocialVideoAutoCollector(
            app.state.session_factory,
            settings=settings,
            interval_seconds=settings.social_video_auto_collect_interval_seconds,
        )
        collector.start()
    if settings.environment != "test" and settings.changzhou_news_auto_collect_enabled:
        news_collector = ChangzhouNewsAutoCollector(
            app.state.session_factory,
            settings=settings,
            interval_seconds=settings.changzhou_news_auto_collect_interval_seconds,
        )
        news_collector.start()
    try:
        yield
    finally:
        if collector is not None:
            await collector.stop()
        if news_collector is not None:
            await news_collector.stop()
    await app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    app = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        debug=resolved.debug,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.engine = create_engine(resolved)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AccessPasswordMiddleware, settings=resolved)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=resolved.cors_allow_credentials,
        allow_methods=resolved.cors_methods,
        allow_headers=resolved.cors_headers,
    )
    app.include_router(health_router, tags=["system"])
    app.include_router(sources_router)
    app.include_router(materials_router)
    app.include_router(collect_tasks_router)
    app.include_router(influencers_router)
    app.include_router(search_router)
    app.include_router(changzhou_news_router)
    app.include_router(social_creators_router)
    app.include_router(social_videos_router)
    app.include_router(wechat_router)
    app.include_router(platform_auth_router)
    return app


app = create_app()
