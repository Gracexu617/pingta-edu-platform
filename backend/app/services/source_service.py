import logging
from datetime import UTC, datetime

from app.domain.source import Source, SourceStatus, SourceType
from app.repositories.source_repository import SourceRepository
from app.repositories.sqlalchemy_source_repository import SourceIntegrityError

logger = logging.getLogger(__name__)


class SourceAlreadyExistsError(ValueError):
    pass


class SourceNotFoundError(LookupError):
    pass


class SourceService:
    def __init__(self, repository: SourceRepository) -> None:
        self._repository = repository

    async def list_sources(self) -> list[Source]:
        return await self._repository.list()

    async def create_source(self, *, name: str, type: SourceType, url: str, note: str) -> Source:
        normalized_name = name.strip()
        if await self._repository.find_by_name(normalized_name):
            raise SourceAlreadyExistsError(f"Source already exists: {normalized_name}")

        now = datetime.now(UTC)
        try:
            source = await self._repository.create(
                Source(
                    id=0,
                    name=normalized_name,
                    type=type,
                    url=url.strip(),
                    note=note.strip(),
                    status=SourceStatus.ENABLED,
                    created_at=now,
                    updated_at=now,
                )
            )
        except SourceIntegrityError as exc:
            raise SourceAlreadyExistsError(f"Source already exists: {normalized_name}") from exc
        logger.info("source_created", extra={"source_id": source.id, "source_name": source.name})
        return source

    async def update_source(
        self,
        source_id: int,
        *,
        name: str | None = None,
        type: SourceType | None = None,
        url: str | None = None,
        note: str | None = None,
        status: SourceStatus | None = None,
    ) -> Source:
        source = await self._repository.get(source_id)
        if not source:
            raise SourceNotFoundError(f"Source not found: {source_id}")

        if name is not None:
            existing = await self._repository.find_by_name(name)
            if existing and existing.id != source_id:
                raise SourceAlreadyExistsError(f"Source already exists: {name}")

        try:
            updated = await self._repository.update(
                source.update(
                    name=name.strip() if name is not None else None,
                    type=type,
                    url=url.strip() if url is not None else None,
                    note=note.strip() if note is not None else None,
                    status=status,
                )
            )
        except SourceIntegrityError as exc:
            raise SourceAlreadyExistsError(f"Source already exists: {name}") from exc
        logger.info("source_updated", extra={"source_id": updated.id, "source_name": updated.name})
        return updated
