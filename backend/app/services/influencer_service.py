from datetime import UTC, datetime

from app.domain.influencer import Influencer, InfluencerContent, InfluencerPlatform
from app.repositories.influencer_repository import InfluencerRepository
from app.repositories.sqlalchemy_influencer_repository import InfluencerIntegrityError


class InfluencerAlreadyExistsError(ValueError):
    pass


class InfluencerNotFoundError(LookupError):
    pass


def pick_phrases(text: str, candidates: list[str]) -> list[str]:
    return [item for item in candidates if item in text][:6]


def summarize(text: str) -> str:
    return " ".join(text.split())[:180]


CORE_VIEW_CANDIDATES = ["择校", "升学", "政策", "中考", "学区", "民办"]
STYLE_CANDIDATES = ["直接", "清单", "误区", "建议", "案例", "提醒"]
TOPIC_CANDIDATES = ["常州", "学校", "招生", "考试", "家长", "录取"]
QUESTION_CANDIDATES = ["怎么选", "要不要", "怎么办", "能不能", "适合谁"]


class InfluencerService:
    def __init__(self, repository: InfluencerRepository) -> None:
        self._repository = repository

    async def list_influencers(self) -> list[Influencer]:
        return await self._repository.list()

    async def create_influencer(
        self,
        *,
        name: str,
        platform: InfluencerPlatform,
        profile_url: str,
        note: str,
    ) -> Influencer:
        if await self._repository.find_by_name(name.strip()):
            raise InfluencerAlreadyExistsError(f"Influencer already exists: {name}")
        now = datetime.now(UTC)
        try:
            return await self._repository.create(
                Influencer(
                    id=0,
                    name=name.strip(),
                    platform=platform,
                    profile_url=profile_url.strip(),
                    note=note.strip(),
                    core_views=[],
                    style_traits=[],
                    common_topics=[],
                    parent_questions=[],
                    content_count=0,
                    created_at=now,
                    updated_at=now,
                )
            )
        except InfluencerIntegrityError as exc:
            raise InfluencerAlreadyExistsError(f"Influencer already exists: {name}") from exc

    async def add_content(
        self,
        *,
        influencer_id: int,
        title: str,
        url: str,
        content: str,
    ) -> tuple[Influencer, InfluencerContent]:
        influencer = await self._repository.get(influencer_id)
        if not influencer:
            raise InfluencerNotFoundError(f"Influencer not found: {influencer_id}")
        stored = await self._repository.add_content(
            InfluencerContent(
                id=0,
                influencer_id=influencer_id,
                title=title.strip(),
                url=url.strip(),
                content=content.strip(),
                summary=summarize(content),
                created_at=datetime.now(UTC),
            )
        )
        contents = await self._repository.list_contents(influencer_id)
        profile_text = "\n".join(item.content for item in contents)
        updated = await self._repository.update(
            influencer.update_profile(
                core_views=pick_phrases(profile_text, CORE_VIEW_CANDIDATES),
                style_traits=pick_phrases(profile_text, STYLE_CANDIDATES),
                common_topics=pick_phrases(profile_text, TOPIC_CANDIDATES),
                parent_questions=pick_phrases(profile_text, QUESTION_CANDIDATES),
                content_count=len(contents),
            )
        )
        return updated, stored
