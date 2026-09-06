from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.database import get_db_session
from app.repositories.sqlalchemy_changzhou_news_repository import (
    SQLAlchemyChangzhouNewsRepository,
)
from app.schemas.changzhou_news import (
    ChangzhouNewsCollectResponse,
    ChangzhouNewsCreateRequest,
    ChangzhouNewsListResponse,
    ChangzhouNewsResponse,
)
from app.services.changzhou_news_service import ChangzhouNewsService

router = APIRouter(prefix="/api/v1/changzhou-news", tags=["changzhou-news"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def build_news_service(session: DbSessionDep) -> ChangzhouNewsService:
    return ChangzhouNewsService(SQLAlchemyChangzhouNewsRepository(session))


NewsServiceDep = Annotated[ChangzhouNewsService, Depends(build_news_service)]


@router.get("", response_model=ChangzhouNewsListResponse)
async def list_news(service: NewsServiceDep) -> ChangzhouNewsListResponse:
    return ChangzhouNewsListResponse(
        items=[ChangzhouNewsResponse.model_validate(item) for item in await service.list_news()]
    )


@router.post("", response_model=ChangzhouNewsResponse, status_code=status.HTTP_201_CREATED)
async def create_news(
    payload: ChangzhouNewsCreateRequest,
    service: NewsServiceDep,
) -> ChangzhouNewsResponse:
    item = await service.create_news(
        title=payload.title,
        category=payload.category,
        source_name=payload.source_name,
        url=payload.url,
        summary=payload.summary,
        published_at=payload.published_at,
    )
    return ChangzhouNewsResponse.model_validate(item)


@router.post("/collect", response_model=ChangzhouNewsCollectResponse, status_code=status.HTTP_200_OK)
async def collect_news(
    service: NewsServiceDep,
    settings: SettingsDep,
) -> ChangzhouNewsCollectResponse:
    """触发一次实时采集：跑各公开源 → 去重 → 入库。前端每 5 分钟自动调用。"""
    result = await service.collect_news(settings)
    return ChangzhouNewsCollectResponse(
        discovered=result.discovered,
        duplicate_skipped=result.duplicate_skipped,
        created=result.created,
        items=[ChangzhouNewsResponse.model_validate(item) for item in result.items],
    )
