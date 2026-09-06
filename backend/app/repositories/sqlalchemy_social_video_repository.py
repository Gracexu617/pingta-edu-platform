from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.social_video import SocialVideo, SocialVideoPlatform, SocialVideoScope
from app.models.social_video import SocialVideoModel


def _to_domain(model: SocialVideoModel) -> SocialVideo:
    return SocialVideo(
        id=model.id,
        title=model.title,
        creator=model.creator,
        platform=SocialVideoPlatform(model.platform),
        scope=SocialVideoScope(model.scope),
        original_url=model.original_url,
        play_url=model.play_url or "",
        likes=model.likes,
        saves=model.saves,
        threshold=model.threshold,
        is_hot=model.is_hot,
        reason=model.reason,
        transcript=model.transcript,
        transcript_source=model.transcript_source,
        transcript_updated_at=model.transcript_updated_at,
        manuscript=model.manuscript,
        published_at=model.published_at,
        collected_at=model.collected_at,
    )


class SQLAlchemySocialVideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[SocialVideo]:
        result = await self._session.execute(
            select(SocialVideoModel).order_by(
                SocialVideoModel.is_hot.desc(),
                SocialVideoModel.collected_at.desc(),
                SocialVideoModel.id.desc(),
            )
        )
        return [_to_domain(model) for model in result.scalars()]

    async def find_by_id(self, video_id: int) -> SocialVideo | None:
        result = await self._session.execute(
            select(SocialVideoModel).where(SocialVideoModel.id == video_id)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_by_url(self, url: str) -> SocialVideo | None:
        result = await self._session.execute(
            select(SocialVideoModel).where(SocialVideoModel.original_url == url)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def create(self, item: SocialVideo) -> SocialVideo:
        model = SocialVideoModel(
            title=item.title,
            creator=item.creator,
            platform=item.platform.value,
            scope=item.scope.value,
            original_url=item.original_url,
            play_url=item.play_url or "",
            likes=item.likes,
            saves=item.saves,
            threshold=item.threshold,
            is_hot=item.is_hot,
            reason=item.reason,
            transcript=item.transcript,
            transcript_source=item.transcript_source,
            transcript_updated_at=item.transcript_updated_at,
            manuscript=item.manuscript,
            published_at=item.published_at,
            collected_at=item.collected_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def update_transcript(
        self,
        video_id: int,
        *,
        transcript: str,
        transcript_source: str,
        manuscript: str = "",
    ) -> SocialVideo | None:
        result = await self._session.execute(
            select(SocialVideoModel).where(SocialVideoModel.id == video_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.transcript = transcript
        model.transcript_source = transcript_source
        model.manuscript = manuscript
        model.transcript_updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_domain(model)

    async def update_manuscript(
        self,
        video_id: int,
        manuscript: str,
    ) -> SocialVideo | None:
        result = await self._session.execute(
            select(SocialVideoModel).where(SocialVideoModel.id == video_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.manuscript = manuscript
        model.transcript_updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_domain(model)

    async def update_play_url(
        self,
        video_id: int,
        *,
        play_url: str,
    ) -> SocialVideo | None:
        result = await self._session.execute(
            select(SocialVideoModel).where(SocialVideoModel.id == video_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.play_url = play_url
        await self._session.flush()
        return _to_domain(model)

    async def update_hot_flags(
        self,
        video_id: int,
        *,
        is_hot: bool,
        threshold: str,
        reason: str,
    ) -> SocialVideo | None:
        result = await self._session.execute(
            select(SocialVideoModel).where(SocialVideoModel.id == video_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.is_hot = is_hot
        model.threshold = threshold
        model.reason = reason
        await self._session.flush()
        return _to_domain(model)
