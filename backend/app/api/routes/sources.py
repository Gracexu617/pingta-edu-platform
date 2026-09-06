from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_source_repository import SQLAlchemySourceRepository
from app.schemas.source import (
    SourceCreateRequest,
    SourceListResponse,
    SourceResponse,
    SourceUpdateRequest,
)
from app.services.source_service import SourceAlreadyExistsError, SourceNotFoundError, SourceService

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def build_source_service(session: DbSessionDep) -> SourceService:
    return SourceService(SQLAlchemySourceRepository(session))


SourceServiceDep = Annotated[SourceService, Depends(build_source_service)]


@router.get("", response_model=SourceListResponse)
async def list_sources(service: SourceServiceDep) -> SourceListResponse:
    return SourceListResponse(
        items=[SourceResponse.model_validate(source) for source in await service.list_sources()]
    )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreateRequest,
    service: SourceServiceDep,
) -> SourceResponse:
    try:
        source = await service.create_source(
            name=payload.name,
            type=payload.type,
            url=payload.url,
            note=payload.note,
        )
    except SourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SourceResponse.model_validate(source)


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    payload: SourceUpdateRequest,
    service: SourceServiceDep,
) -> SourceResponse:
    try:
        source = await service.update_source(
            source_id,
            name=payload.name,
            type=payload.type,
            url=payload.url,
            note=payload.note,
            status=payload.status,
        )
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SourceResponse.model_validate(source)
