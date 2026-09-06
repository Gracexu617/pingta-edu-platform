from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.material import Material, MaterialStatus
from app.domain.source import SourceType
from app.models.material import MaterialModel


def _to_domain(model: MaterialModel) -> Material:
    return Material(
        id=model.id,
        title=model.title,
        source=SourceType(model.source),
        source_name=model.source_name,
        source_id=model.source_id,
        url=model.url,
        tags=list(model.tags),
        keywords=list(model.keywords or []),
        summary=model.summary,
        content=model.content,
        status=MaterialStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyMaterialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[Material]:
        result = await self._session.execute(
            select(MaterialModel).order_by(MaterialModel.id.desc())
        )
        return [_to_domain(model) for model in result.scalars()]

    async def get(self, material_id: int) -> Material | None:
        model = await self._session.get(MaterialModel, material_id)
        return _to_domain(model) if model else None

    async def create(self, material: Material) -> Material:
        model = MaterialModel(
            title=material.title,
            source=material.source.value,
            source_name=material.source_name,
            source_id=material.source_id,
            url=material.url,
            tags=material.tags,
            keywords=material.keywords,
            summary=material.summary,
            content=material.content,
            status=material.status.value,
            created_at=material.created_at,
            updated_at=material.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def update(self, material: Material) -> Material:
        model = await self._session.get(MaterialModel, material.id)
        if model is None:
            raise LookupError(f"Material not found: {material.id}")
        model.title = material.title
        model.tags = material.tags
        model.keywords = material.keywords
        model.summary = material.summary
        model.content = material.content
        model.status = material.status.value
        model.updated_at = material.updated_at
        await self._session.flush()
        return _to_domain(model)
