from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_material_repository import SQLAlchemyMaterialRepository
from app.schemas.material import (
    MaterialCreateRequest,
    MaterialListResponse,
    MaterialResponse,
    MaterialUpdateRequest,
)
from app.services.material_processor import MaterialProcessorService
from app.services.material_service import MaterialNotFoundError, MaterialService

router = APIRouter(prefix="/api/v1/materials", tags=["materials"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def build_material_service(session: DbSessionDep) -> MaterialService:
    return MaterialService(SQLAlchemyMaterialRepository(session))


MaterialServiceDep = Annotated[MaterialService, Depends(build_material_service)]


def build_material_processor(session: DbSessionDep) -> MaterialProcessorService:
    return MaterialProcessorService(SQLAlchemyMaterialRepository(session))


MaterialProcessorDep = Annotated[MaterialProcessorService, Depends(build_material_processor)]


@router.get("", response_model=MaterialListResponse)
async def list_materials(service: MaterialServiceDep) -> MaterialListResponse:
    return MaterialListResponse(
        items=[MaterialResponse.model_validate(item) for item in await service.list_materials()]
    )


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    payload: MaterialCreateRequest,
    service: MaterialServiceDep,
) -> MaterialResponse:
    material = await service.create_material(
        title=payload.title,
        source=payload.source,
        source_name=payload.source_name,
        source_id=payload.source_id,
        url=payload.url,
        tags=payload.tags,
        keywords=payload.keywords,
        summary=payload.summary,
        content=payload.content,
    )
    return MaterialResponse.model_validate(material)


@router.patch("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: int,
    payload: MaterialUpdateRequest,
    service: MaterialServiceDep,
) -> MaterialResponse:
    try:
        material = await service.update_material(
            material_id,
            title=payload.title,
            tags=payload.tags,
            keywords=payload.keywords,
            summary=payload.summary,
            content=payload.content,
            status=payload.status,
        )
    except MaterialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MaterialResponse.model_validate(material)


@router.post("/{material_id}/process", response_model=MaterialResponse)
async def process_material(
    material_id: int,
    service: MaterialProcessorDep,
) -> MaterialResponse:
    try:
        material = await service.process(material_id)
    except MaterialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MaterialResponse.model_validate(material)
