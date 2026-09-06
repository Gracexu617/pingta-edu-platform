from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collect_task import CollectTask, CollectTaskStatus
from app.domain.source import SourceType
from app.models.collect_task import CollectTaskModel


def _to_domain(model: CollectTaskModel) -> CollectTask:
    return CollectTask(
        id=model.id,
        source_id=model.source_id,
        source_name=model.source_name,
        source_type=SourceType(model.source_type),
        url=model.url,
        goal=model.goal,
        status=CollectTaskStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyCollectTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[CollectTask]:
        result = await self._session.execute(
            select(CollectTaskModel).order_by(CollectTaskModel.id.desc())
        )
        return [_to_domain(model) for model in result.scalars()]

    async def get(self, task_id: int) -> CollectTask | None:
        model = await self._session.get(CollectTaskModel, task_id)
        return _to_domain(model) if model else None

    async def create(self, task: CollectTask) -> CollectTask:
        model = CollectTaskModel(
            source_id=task.source_id,
            source_name=task.source_name,
            source_type=task.source_type.value,
            url=task.url,
            goal=task.goal,
            status=task.status.value,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def update(self, task: CollectTask) -> CollectTask:
        model = await self._session.get(CollectTaskModel, task.id)
        if model is None:
            raise LookupError(f"Task not found: {task.id}")
        model.status = task.status.value
        model.updated_at = task.updated_at
        await self._session.flush()
        return _to_domain(model)
