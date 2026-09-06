from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.domain.changzhou_news import ChangzhouNews, NewsImportance
from app.models.changzhou_news import ChangzhouNewsModel


def _to_domain(model: ChangzhouNewsModel) -> ChangzhouNews:
    return ChangzhouNews(
        id=model.id,
        title=model.title,
        category=model.category,
        source_name=model.source_name,
        url=model.url,
        summary=model.summary,
        importance=NewsImportance(model.importance),
        published_at=model.published_at,
        created_at=model.created_at,
    )


class SQLAlchemyChangzhouNewsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[ChangzhouNews]:
        result = await self._session.execute(
            select(ChangzhouNewsModel).order_by(
                ChangzhouNewsModel.published_at.desc(),
                ChangzhouNewsModel.id.desc(),
            )
        )
        return [_to_domain(model) for model in result.scalars()]

    async def create(self, item: ChangzhouNews) -> ChangzhouNews:
        model = ChangzhouNewsModel(
            title=item.title,
            category=item.category,
            source_name=item.source_name,
            url=item.url,
            summary=item.summary,
            importance=item.importance.value,
            published_at=item.published_at,
            created_at=item.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def exists_by_url(self, url: str) -> bool:
        from app.services.changzhou_news_collector import normalize_url

        target = normalize_url(url)
        result = await self._session.execute(
            select(func.count())
            .select_from(ChangzhouNewsModel)
            .where(ChangzhouNewsModel.url == target)
        )
        return (result.scalar() or 0) > 0
