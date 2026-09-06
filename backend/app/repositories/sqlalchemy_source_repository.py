from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.source import Source, SourceStatus, SourceType
from app.models.source import SourceModel


class SourceIntegrityError(ValueError):
    pass


def _to_domain(model: SourceModel) -> Source:
    return Source(
        id=model.id,
        name=model.name,
        type=SourceType(model.type),
        url=model.url,
        note=model.note,
        status=SourceStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemySourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[Source]:
        result = await self._session.execute(select(SourceModel).order_by(SourceModel.id))
        return [_to_domain(model) for model in result.scalars()]

    async def get(self, source_id: int) -> Source | None:
        model = await self._session.get(SourceModel, source_id)
        return _to_domain(model) if model else None

    async def find_by_name(self, name: str) -> Source | None:
        result = await self._session.execute(
            select(SourceModel).where(SourceModel.name == name.strip())
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def create(self, source: Source) -> Source:
        model = SourceModel(
            name=source.name,
            type=source.type.value,
            url=source.url,
            note=source.note,
            status=source.status.value,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise SourceIntegrityError from exc
        return _to_domain(model)

    async def update(self, source: Source) -> Source:
        model = await self._session.get(SourceModel, source.id)
        if model is None:
            raise LookupError(f"Source not found: {source.id}")

        model.name = source.name
        model.type = source.type.value
        model.url = source.url
        model.note = source.note
        model.status = source.status.value
        model.updated_at = source.updated_at
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise SourceIntegrityError from exc
        return _to_domain(model)
