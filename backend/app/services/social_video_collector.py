import asyncio
import contextlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.repositories.sqlalchemy_social_creator_repository import SQLAlchemySocialCreatorRepository
from app.repositories.sqlalchemy_social_video_repository import SQLAlchemySocialVideoRepository
from app.services.social_video_service import SocialVideoService
from app.services.verified_video_provider import build_verified_video_provider

logger = logging.getLogger(__name__)


class SocialVideoAutoCollector:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        settings: Settings,
        interval_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="social-video-auto-collector")
        logger.info(
            "social_video_auto_collector_started",
            extra={"interval": self._interval_seconds},
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        logger.info("social_video_auto_collector_stopped")

    async def collect_once(self) -> int:
        async with self._session_factory() as session:
            service = SocialVideoService(
                SQLAlchemySocialVideoRepository(session),
                SQLAlchemySocialCreatorRepository(session),
                verified_video_provider=build_verified_video_provider(self._settings),
            )
            items = await service.collect_public_videos()
            await session.commit()
            return len(items)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                created = await self.collect_once()
                logger.info(
                    "social_video_auto_collect_finished",
                    extra={"created_count": created},
                )
            except Exception:
                logger.exception("social_video_auto_collect_failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                continue
