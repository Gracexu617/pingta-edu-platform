from datetime import UTC, datetime

from app.domain.social_creator import SocialCreator, SocialCreatorCategory
from app.domain.social_video import SocialVideoPlatform, SocialVideoScope
from app.repositories.social_creator_repository import SocialCreatorRepository
from app.repositories.sqlalchemy_social_creator_repository import SocialCreatorIntegrityError


class SocialCreatorAlreadyExistsError(ValueError):
    pass


class SocialCreatorNotFoundError(ValueError):
    pass


DEFAULT_KEYWORDS = ["高考", "升学", "志愿填报", "专业选择", "家长"]


def normalize_keywords(keywords: list[str]) -> list[str]:
    normalized = [item.strip() for item in keywords if item.strip()]
    return normalized or DEFAULT_KEYWORDS


class SocialCreatorService:
    def __init__(self, repository: SocialCreatorRepository) -> None:
        self._repository = repository

    async def list_creators(self) -> list[SocialCreator]:
        return await self._repository.list()

    async def create_creator(
        self,
        *,
        name: str,
        platform: SocialVideoPlatform,
        scope: SocialVideoScope,
        category: SocialCreatorCategory,
        profile_url: str,
        keywords: list[str],
    ) -> SocialCreator:
        normalized_name = name.strip()
        if await self._repository.find_by_name(normalized_name):
            raise SocialCreatorAlreadyExistsError(f"Creator already exists: {normalized_name}")
        now = datetime.now(UTC)
        try:
            return await self._repository.create(
                SocialCreator(
                    id=0,
                    name=normalized_name,
                    platform=platform,
                    scope=scope,
                    category=category,
                    profile_url=profile_url.strip(),
                    keywords=normalize_keywords(keywords),
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        except SocialCreatorIntegrityError as exc:
            message = f"Creator already exists: {normalized_name}"
            raise SocialCreatorAlreadyExistsError(message) from exc

    async def update_creator(
        self,
        *,
        creator_id: int,
        platform: SocialVideoPlatform | None = None,
        scope: SocialVideoScope | None = None,
        category: SocialCreatorCategory | None = None,
        profile_url: str | None = None,
        keywords: list[str] | None = None,
        enabled: bool | None = None,
    ) -> SocialCreator:
        existing = await self._repository.find_by_id(creator_id)
        if existing is None:
            raise SocialCreatorNotFoundError(f"Creator not found: {creator_id}")
        return await self._repository.update(
            SocialCreator(
                id=existing.id,
                name=existing.name,
                platform=platform or existing.platform,
                scope=scope or existing.scope,
                category=category or existing.category,
                profile_url=existing.profile_url if profile_url is None else profile_url.strip(),
                keywords=existing.keywords if keywords is None else normalize_keywords(keywords),
                enabled=existing.enabled if enabled is None else enabled,
                created_at=existing.created_at,
                updated_at=datetime.now(UTC),
            )
        )
