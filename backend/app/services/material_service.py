from datetime import UTC, datetime

from app.domain.material import Material, MaterialStatus
from app.domain.source import SourceType
from app.repositories.material_repository import MaterialRepository


class MaterialNotFoundError(LookupError):
    pass


class MaterialService:
    def __init__(self, repository: MaterialRepository) -> None:
        self._repository = repository

    async def list_materials(self) -> list[Material]:
        return await self._repository.list()

    async def create_material(
        self,
        *,
        title: str,
        source: SourceType,
        source_name: str | None,
        source_id: int | None,
        url: str,
        tags: list[str],
        keywords: list[str] | None = None,
        summary: str,
        content: str,
    ) -> Material:
        now = datetime.now(UTC)
        return await self._repository.create(
            Material(
                id=0,
                title=title.strip(),
                source=source,
                source_name=source_name.strip() if source_name else None,
                source_id=source_id,
                url=url.strip(),
                tags=[tag.strip() for tag in tags if tag.strip()] or ["待标注"],
                keywords=[keyword.strip() for keyword in (keywords or []) if keyword.strip()],
                summary=summary.strip() or content.strip()[:120],
                content=content.strip(),
                status=MaterialStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
        )

    async def update_material(
        self,
        material_id: int,
        *,
        title: str | None = None,
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
        summary: str | None = None,
        content: str | None = None,
        status: MaterialStatus | None = None,
    ) -> Material:
        material = await self._repository.get(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material not found: {material_id}")
        return await self._repository.update(
            material.update(
                title=title.strip() if title is not None else None,
                tags=[tag.strip() for tag in tags if tag.strip()] if tags is not None else None,
                keywords=[item.strip() for item in keywords if item.strip()]
                if keywords is not None
                else None,
                summary=summary.strip() if summary is not None else None,
                content=content.strip() if content is not None else None,
                status=status,
            )
        )
