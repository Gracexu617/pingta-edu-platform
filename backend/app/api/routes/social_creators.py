from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_social_creator_repository import SQLAlchemySocialCreatorRepository
from app.schemas.social_creator import (
    SocialCreatorCreateRequest,
    SocialCreatorListResponse,
    SocialCreatorResponse,
    SocialCreatorUpdateRequest,
)
from app.services.social_creator_service import (
    SocialCreatorAlreadyExistsError,
    SocialCreatorNotFoundError,
    SocialCreatorService,
)

router = APIRouter(prefix="/api/v1/social-creators", tags=["social-creators"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def build_social_creator_service(session: DbSessionDep) -> SocialCreatorService:
    return SocialCreatorService(SQLAlchemySocialCreatorRepository(session))


SocialCreatorServiceDep = Annotated[SocialCreatorService, Depends(build_social_creator_service)]


@router.get("", response_model=SocialCreatorListResponse)
async def list_social_creators(service: SocialCreatorServiceDep) -> SocialCreatorListResponse:
    return SocialCreatorListResponse(
        items=[
            SocialCreatorResponse.model_validate(item)
            for item in await service.list_creators()
        ]
    )


@router.post("", response_model=SocialCreatorResponse, status_code=status.HTTP_201_CREATED)
async def create_social_creator(
    payload: SocialCreatorCreateRequest,
    service: SocialCreatorServiceDep,
) -> SocialCreatorResponse:
    try:
        item = await service.create_creator(
            name=payload.name,
            platform=payload.platform,
            scope=payload.scope,
            category=payload.category,
            profile_url=payload.profile_url,
            keywords=payload.keywords,
        )
    except SocialCreatorAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SocialCreatorResponse.model_validate(item)


@router.patch("/{creator_id}", response_model=SocialCreatorResponse)
async def update_social_creator(
    creator_id: int,
    payload: SocialCreatorUpdateRequest,
    service: SocialCreatorServiceDep,
) -> SocialCreatorResponse:
    try:
        item = await service.update_creator(
            creator_id=creator_id,
            platform=payload.platform,
            scope=payload.scope,
            category=payload.category,
            profile_url=payload.profile_url,
            keywords=payload.keywords,
            enabled=payload.enabled,
        )
    except SocialCreatorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SocialCreatorResponse.model_validate(item)
