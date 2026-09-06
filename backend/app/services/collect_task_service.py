from datetime import UTC, datetime

from app.domain.collect_task import CollectTask, CollectTaskStatus
from app.domain.material import Material, MaterialStatus
from app.domain.source import Source
from app.repositories.collect_task_repository import CollectTaskRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.source_repository import SourceRepository
from app.services.content_fetcher import ContentFetchError, HttpxContentFetcher


class CollectTaskNotFoundError(LookupError):
    pass


class CollectTaskSourceNotFoundError(LookupError):
    pass


class CollectTaskExecutionError(RuntimeError):
    pass


class CollectTaskService:
    def __init__(
        self,
        task_repository: CollectTaskRepository,
        source_repository: SourceRepository,
    ) -> None:
        self._task_repository = task_repository
        self._source_repository = source_repository

    async def list_tasks(self) -> list[CollectTask]:
        return await self._task_repository.list()

    async def create_task_from_source(self, source_id: int) -> CollectTask:
        source = await self._source_repository.get(source_id)
        if not source:
            raise CollectTaskSourceNotFoundError(f"Source not found: {source_id}")
        return await self.create_task(source)

    async def create_task(self, source: Source) -> CollectTask:
        now = datetime.now(UTC)
        return await self._task_repository.create(
            CollectTask(
                id=0,
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                url=source.url,
                goal=source.note or f"采集{source.name}的新内容",
                status=CollectTaskStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
        )

    async def update_task(self, task_id: int, *, status: CollectTaskStatus) -> CollectTask:
        task = await self._task_repository.get(task_id)
        if not task:
            raise CollectTaskNotFoundError(f"Task not found: {task_id}")
        return await self._task_repository.update(task.update(status=status))


class CollectTaskExecutorService:
    def __init__(
        self,
        task_repository: CollectTaskRepository,
        material_repository: MaterialRepository,
        fetcher: HttpxContentFetcher,
    ) -> None:
        self._task_repository = task_repository
        self._material_repository = material_repository
        self._fetcher = fetcher

    async def execute(self, task_id: int) -> tuple[CollectTask, Material]:
        task = await self._task_repository.get(task_id)
        if not task:
            raise CollectTaskNotFoundError(f"Task not found: {task_id}")

        processing = await self._task_repository.update(
            task.update(status=CollectTaskStatus.PROCESSING)
        )
        try:
            fetched = await self._fetcher.fetch(processing.url, processing.source_name)
        except ContentFetchError as exc:
            raise CollectTaskExecutionError(str(exc)) from exc

        now = datetime.now(UTC)
        material = await self._material_repository.create(
            Material(
                id=0,
                title=fetched.title,
                source=processing.source_type,
                source_name=processing.source_name,
                source_id=processing.source_id,
                url=processing.url,
                tags=fetched.tags,
                keywords=[],
                summary=fetched.content[:120],
                content=fetched.content,
                status=MaterialStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
        )
        done = await self._task_repository.update(processing.update(status=CollectTaskStatus.DONE))
        return done, material
