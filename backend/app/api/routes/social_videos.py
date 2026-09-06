import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_social_creator_repository import SQLAlchemySocialCreatorRepository
from app.repositories.sqlalchemy_social_video_repository import SQLAlchemySocialVideoRepository
from app.schemas.social_video import (
    HotThresholdItem,
    HotThresholdResponse,
    HotThresholdUpdateRequest,
    SocialVideoCollectionLogListResponse,
    SocialVideoCollectionLogResponse,
    SocialVideoCollectResponse,
    SocialVideoCreateRequest,
    SocialVideoListResponse,
    SocialVideoResponse,
)
from app.services.social_video_service import (
    SocialVideoService,
    list_collection_logs,
    video_recommendation_score,
)
from app.services.social_video_transcript_provider import (
    build_local_file_transcript_provider,
    build_social_video_transcript_provider,
)
from app.services.verified_video_provider import build_verified_video_provider

router = APIRouter(prefix="/api/v1/social-videos", tags=["social-videos"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
TranscriptUploadDep = Annotated[UploadFile, File(...)]


def _to_hot_threshold_items(data: dict) -> list[HotThresholdItem]:
    items: list[HotThresholdItem] = []
    for key, values in data["thresholds"].items():
        platform, scope = key.split("|", maxsplit=1)
        items.append(
            HotThresholdItem(
                platform=platform,
                scope=scope,
                likes=values["likes"],
                saves=values["saves"],
            )
        )
    return items


def build_social_video_service(session: DbSessionDep, request: Request) -> SocialVideoService:
    settings = request.app.state.settings
    return SocialVideoService(
        SQLAlchemySocialVideoRepository(session),
        SQLAlchemySocialCreatorRepository(session),
        verified_video_provider=build_verified_video_provider(settings),
        transcript_provider=build_social_video_transcript_provider(settings),
        local_transcript_provider=build_local_file_transcript_provider(settings),
        settings=settings,
    )


SocialVideoServiceDep = Annotated[SocialVideoService, Depends(build_social_video_service)]


def to_social_video_response(item) -> SocialVideoResponse:
    return SocialVideoResponse.model_validate(item).model_copy(
        update={"recommendation_score": video_recommendation_score(item)}
    )


@router.get("", response_model=SocialVideoListResponse)
async def list_social_videos(service: SocialVideoServiceDep) -> SocialVideoListResponse:
    return SocialVideoListResponse(
        items=[to_social_video_response(item) for item in await service.list_videos()]
    )


@router.get("/hot-thresholds", response_model=HotThresholdResponse)
async def get_hot_thresholds() -> HotThresholdResponse:
    """返回当前 4 个 (平台×范围) 组合的推送门槛。"""
    from app.services.hot_threshold_store import load

    data = load()
    return HotThresholdResponse(items=_to_hot_threshold_items(data))


@router.put("/hot-thresholds", response_model=HotThresholdResponse)
async def update_hot_thresholds(
    payload: HotThresholdUpdateRequest,
    service: SocialVideoServiceDep,
) -> HotThresholdResponse:
    """保存新的推送门槛，并按新标准重算所有已采集视频的 is_hot 标记。"""
    from app.services.hot_threshold_store import load, save

    incoming = {
        f"{item.platform}|{item.scope}": {"likes": item.likes, "saves": item.saves}
        for item in payload.items
    }
    save(incoming)
    await service.recompute_hot_flags()
    data = load()
    return HotThresholdResponse(items=_to_hot_threshold_items(data))


@router.post("", response_model=SocialVideoResponse, status_code=status.HTTP_201_CREATED)
async def create_social_video(
    payload: SocialVideoCreateRequest,
    service: SocialVideoServiceDep,
) -> SocialVideoResponse:
    item = await service.create_video(
        title=payload.title,
        creator=payload.creator,
        platform=payload.platform,
        scope=payload.scope,
        original_url=str(payload.original_url),
        likes=payload.likes,
        saves=payload.saves,
        published_at=payload.published_at,
    )
    return to_social_video_response(item)


@router.post("/collect-public", response_model=SocialVideoCollectResponse)
async def collect_public_social_videos(
    service: SocialVideoServiceDep,
) -> SocialVideoCollectResponse:
    items = await service.collect_public_videos()
    return SocialVideoCollectResponse(
        created=len(items),
        items=[to_social_video_response(item) for item in items],
    )


@router.get("/collection-logs", response_model=SocialVideoCollectionLogListResponse)
async def list_social_video_collection_logs() -> SocialVideoCollectionLogListResponse:
    return SocialVideoCollectionLogListResponse(
        items=[
            SocialVideoCollectionLogResponse.model_validate(item)
            for item in list_collection_logs()
        ]
    )


@router.post("/{video_id}/transcript", response_model=SocialVideoResponse)
async def generate_social_video_transcript(
    video_id: int,
    service: SocialVideoServiceDep,
) -> SocialVideoResponse:
    item = await service.generate_transcript(video_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return to_social_video_response(item)


@router.post("/{video_id}/transcript-from-file", response_model=SocialVideoResponse)
async def generate_social_video_transcript_from_file(
    video_id: int,
    service: SocialVideoServiceDep,
    file: TranscriptUploadDep,
) -> SocialVideoResponse:
    """方案 C：上传本地已下载的抖音音频/视频文件，离线转写（不依赖 TikHub）。
    文件仅临时落盘供 Whisper 读取，转写完成立即删除，仅保留文字结果。"""
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        item = await service.generate_transcript_from_local(video_id, tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return to_social_video_response(item)


@router.post("/{video_id}/manuscript", response_model=SocialVideoResponse)
async def regenerate_social_video_manuscript(
    video_id: int,
    service: SocialVideoServiceDep,
) -> SocialVideoResponse:
    item = await service.regenerate_manuscript(video_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return to_social_video_response(item)
