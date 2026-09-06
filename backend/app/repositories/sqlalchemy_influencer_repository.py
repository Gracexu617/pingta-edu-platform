from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.influencer import Influencer, InfluencerContent, InfluencerPlatform
from app.models.influencer import InfluencerContentModel, InfluencerModel


class InfluencerIntegrityError(ValueError):
    pass


def _to_influencer(model: InfluencerModel) -> Influencer:
    return Influencer(
        id=model.id,
        name=model.name,
        platform=InfluencerPlatform(model.platform),
        profile_url=model.profile_url,
        note=model.note,
        core_views=list(model.core_views),
        style_traits=list(model.style_traits),
        common_topics=list(model.common_topics),
        parent_questions=list(model.parent_questions),
        content_count=model.content_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_content(model: InfluencerContentModel) -> InfluencerContent:
    return InfluencerContent(
        id=model.id,
        influencer_id=model.influencer_id,
        title=model.title,
        url=model.url,
        content=model.content,
        summary=model.summary,
        created_at=model.created_at,
    )


class SQLAlchemyInfluencerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[Influencer]:
        result = await self._session.execute(select(InfluencerModel).order_by(InfluencerModel.id))
        return [_to_influencer(model) for model in result.scalars()]

    async def get(self, influencer_id: int) -> Influencer | None:
        model = await self._session.get(InfluencerModel, influencer_id)
        return _to_influencer(model) if model else None

    async def find_by_name(self, name: str) -> Influencer | None:
        result = await self._session.execute(
            select(InfluencerModel).where(InfluencerModel.name == name.strip())
        )
        model = result.scalar_one_or_none()
        return _to_influencer(model) if model else None

    async def create(self, influencer: Influencer) -> Influencer:
        model = InfluencerModel(
            name=influencer.name,
            platform=influencer.platform.value,
            profile_url=influencer.profile_url,
            note=influencer.note,
            core_views=influencer.core_views,
            style_traits=influencer.style_traits,
            common_topics=influencer.common_topics,
            parent_questions=influencer.parent_questions,
            content_count=influencer.content_count,
            created_at=influencer.created_at,
            updated_at=influencer.updated_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise InfluencerIntegrityError from exc
        return _to_influencer(model)

    async def update(self, influencer: Influencer) -> Influencer:
        model = await self._session.get(InfluencerModel, influencer.id)
        if model is None:
            raise LookupError(f"Influencer not found: {influencer.id}")
        model.core_views = influencer.core_views
        model.style_traits = influencer.style_traits
        model.common_topics = influencer.common_topics
        model.parent_questions = influencer.parent_questions
        model.content_count = influencer.content_count
        model.updated_at = influencer.updated_at
        await self._session.flush()
        return _to_influencer(model)

    async def add_content(self, content: InfluencerContent) -> InfluencerContent:
        model = InfluencerContentModel(
            influencer_id=content.influencer_id,
            title=content.title,
            url=content.url,
            content=content.content,
            summary=content.summary,
            created_at=content.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_content(model)

    async def list_contents(self, influencer_id: int) -> list[InfluencerContent]:
        result = await self._session.execute(
            select(InfluencerContentModel)
            .where(InfluencerContentModel.influencer_id == influencer_id)
            .order_by(InfluencerContentModel.id.desc())
        )
        return [_to_content(model) for model in result.scalars()]
