from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.social_creator import SocialCreator, SocialCreatorCategory
from app.domain.social_video import SocialVideoPlatform, SocialVideoScope
from app.models.social_creator import SocialCreatorModel


class SocialCreatorIntegrityError(ValueError):
    pass


def _to_domain(model: SocialCreatorModel) -> SocialCreator:
    return SocialCreator(
        id=model.id,
        name=model.name,
        platform=SocialVideoPlatform(model.platform),
        scope=SocialVideoScope(model.scope),
        category=SocialCreatorCategory(model.category),
        profile_url=model.profile_url,
        keywords=model.keywords,
        enabled=model.enabled,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemySocialCreatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[SocialCreator]:
        result = await self._session.execute(
            select(SocialCreatorModel).order_by(
                SocialCreatorModel.enabled.desc(),
                SocialCreatorModel.updated_at.desc(),
                SocialCreatorModel.id.desc(),
            )
        )
        return [_to_domain(model) for model in result.scalars()]

    async def find_by_name(self, name: str) -> SocialCreator | None:
        result = await self._session.execute(
            select(SocialCreatorModel).where(SocialCreatorModel.name == name)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_by_id(self, creator_id: int) -> SocialCreator | None:
        model = await self._session.get(SocialCreatorModel, creator_id)
        return _to_domain(model) if model else None

    async def create(self, item: SocialCreator) -> SocialCreator:
        model = SocialCreatorModel(
            name=item.name,
            platform=item.platform.value,
            scope=item.scope.value,
            category=item.category.value,
            profile_url=item.profile_url,
            keywords=item.keywords,
            enabled=item.enabled,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise SocialCreatorIntegrityError(str(exc)) from exc
        return _to_domain(model)

    async def update(self, item: SocialCreator) -> SocialCreator:
        model = await self._session.get(SocialCreatorModel, item.id)
        if model is None:
            raise ValueError(f"Creator not found: {item.id}")
        model.platform = item.platform.value
        model.scope = item.scope.value
        model.category = item.category.value
        model.profile_url = item.profile_url
        model.keywords = item.keywords
        model.enabled = item.enabled
        model.updated_at = item.updated_at
        await self._session.flush()
        return _to_domain(model)
