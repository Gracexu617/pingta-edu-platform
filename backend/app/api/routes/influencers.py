from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_influencer_repository import SQLAlchemyInfluencerRepository
from app.schemas.influencer import (
    InfluencerContentCreateRequest,
    InfluencerContentResponse,
    InfluencerCreateRequest,
    InfluencerDistillResponse,
    InfluencerListResponse,
    InfluencerResponse,
)
from app.services.influencer_service import (
    InfluencerAlreadyExistsError,
    InfluencerNotFoundError,
    InfluencerService,
)

router = APIRouter(prefix="/api/v1/influencers", tags=["influencers"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def build_influencer_service(session: DbSessionDep) -> InfluencerService:
    return InfluencerService(SQLAlchemyInfluencerRepository(session))


InfluencerServiceDep = Annotated[InfluencerService, Depends(build_influencer_service)]


@router.get("", response_model=InfluencerListResponse)
async def list_influencers(service: InfluencerServiceDep) -> InfluencerListResponse:
    return InfluencerListResponse(
        items=[
            InfluencerResponse.model_validate(item)
            for item in await service.list_influencers()
        ]
    )


@router.post("", response_model=InfluencerResponse, status_code=status.HTTP_201_CREATED)
async def create_influencer(
    payload: InfluencerCreateRequest,
    service: InfluencerServiceDep,
) -> InfluencerResponse:
    try:
        influencer = await service.create_influencer(
            name=payload.name,
            platform=payload.platform,
            profile_url=payload.profile_url,
            note=payload.note,
        )
    except InfluencerAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return InfluencerResponse.model_validate(influencer)


@router.post("/{influencer_id}/contents", response_model=InfluencerDistillResponse)
async def add_content(
    influencer_id: int,
    payload: InfluencerContentCreateRequest,
    service: InfluencerServiceDep,
) -> InfluencerDistillResponse:
    try:
        influencer, content = await service.add_content(
            influencer_id=influencer_id,
            title=payload.title,
            url=payload.url,
            content=payload.content,
        )
    except InfluencerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return InfluencerDistillResponse(
        influencer=InfluencerResponse.model_validate(influencer),
        content=InfluencerContentResponse.model_validate(content),
    )
