from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_collect_task_repository import SQLAlchemyCollectTaskRepository
from app.repositories.sqlalchemy_material_repository import SQLAlchemyMaterialRepository
from app.repositories.sqlalchemy_source_repository import SQLAlchemySourceRepository
from app.schemas.collect_task import (
    CollectTaskCreateRequest,
    CollectTaskExecuteResponse,
    CollectTaskListResponse,
    CollectTaskResponse,
    CollectTaskUpdateRequest,
)
from app.schemas.material import MaterialResponse
from app.services.collect_task_service import (
    CollectTaskExecutionError,
    CollectTaskExecutorService,
    CollectTaskNotFoundError,
    CollectTaskService,
    CollectTaskSourceNotFoundError,
)
from app.services.content_fetcher import HttpxContentFetcher

router = APIRouter(prefix="/api/v1/collect-tasks", tags=["collect-tasks"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def build_collect_task_service(session: DbSessionDep) -> CollectTaskService:
    return CollectTaskService(
        SQLAlchemyCollectTaskRepository(session),
        SQLAlchemySourceRepository(session),
    )


CollectTaskServiceDep = Annotated[CollectTaskService, Depends(build_collect_task_service)]


def build_collect_task_executor(session: DbSessionDep) -> CollectTaskExecutorService:
    return CollectTaskExecutorService(
        SQLAlchemyCollectTaskRepository(session),
        SQLAlchemyMaterialRepository(session),
        HttpxContentFetcher(),
    )


CollectTaskExecutorDep = Annotated[CollectTaskExecutorService, Depends(build_collect_task_executor)]


@router.get("", response_model=CollectTaskListResponse)
async def list_tasks(service: CollectTaskServiceDep) -> CollectTaskListResponse:
    return CollectTaskListResponse(
        items=[CollectTaskResponse.model_validate(task) for task in await service.list_tasks()]
    )


@router.post("", response_model=CollectTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: CollectTaskCreateRequest,
    service: CollectTaskServiceDep,
) -> CollectTaskResponse:
    try:
        task = await service.create_task_from_source(payload.source_id)
    except CollectTaskSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CollectTaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=CollectTaskResponse)
async def update_task(
    task_id: int,
    payload: CollectTaskUpdateRequest,
    service: CollectTaskServiceDep,
) -> CollectTaskResponse:
    try:
        task = await service.update_task(task_id, status=payload.status)
    except CollectTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CollectTaskResponse.model_validate(task)


@router.post("/{task_id}/execute", response_model=CollectTaskExecuteResponse)
async def execute_task(
    task_id: int,
    service: CollectTaskExecutorDep,
) -> CollectTaskExecuteResponse:
    try:
        task, material = await service.execute(task_id)
    except CollectTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CollectTaskExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return CollectTaskExecuteResponse(
        task=CollectTaskResponse.model_validate(task),
        material=MaterialResponse.model_validate(material),
    )
