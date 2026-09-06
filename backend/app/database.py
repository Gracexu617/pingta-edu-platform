from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.domain.influencer import InfluencerPlatform
from app.domain.social_creator import SocialCreatorCategory
from app.domain.social_video import SocialVideoPlatform, SocialVideoScope
from app.models.base import Base
from app.repositories.source_repository import default_sources
from app.repositories.sqlalchemy_changzhou_news_repository import SQLAlchemyChangzhouNewsRepository
from app.repositories.sqlalchemy_influencer_repository import SQLAlchemyInfluencerRepository
from app.repositories.sqlalchemy_social_creator_repository import SQLAlchemySocialCreatorRepository
from app.repositories.sqlalchemy_source_repository import SQLAlchemySourceRepository
from app.services.changzhou_news_service import ChangzhouNewsService
from app.services.influencer_service import InfluencerService
from app.services.social_creator_service import SocialCreatorService


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.database_url, echo=settings.database_echo)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def initialize_database(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    auto_create: bool,
) -> None:
    if auto_create:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        # 兼容已有库：新增 manuscript 列（create_all 不会给已存在的表加列）
        async with engine.begin() as connection:
            try:
                await connection.execute(
                    text(
                        "ALTER TABLE social_videos ADD COLUMN manuscript TEXT NOT NULL DEFAULT ''"
                    )
                )
            except Exception:  # noqa: BLE001 - 列已存在时忽略
                pass
        # 兼容已有库：新增 play_url 列（采集时存储视频播放地址，供本地 ASR 使用）
        async with engine.begin() as connection:
            try:
                await connection.execute(
                    text(
                        "ALTER TABLE social_videos ADD COLUMN play_url TEXT NOT NULL DEFAULT ''"
                    )
                )
            except Exception:  # noqa: BLE001 - 列已存在时忽略
                pass

    async with session_factory() as session:
        repository = SQLAlchemySourceRepository(session)
        for source in default_sources():
            if not await repository.find_by_name(source.name):
                await repository.create(source)
        influencer_repository = SQLAlchemyInfluencerRepository(session)
        influencer_service = InfluencerService(influencer_repository)
        if not await influencer_repository.find_by_name("学习指导-亦木老师"):
            await influencer_service.create_influencer(
                name="学习指导-亦木老师",
                platform=InfluencerPlatform.WECHAT_CHANNELS,
                profile_url="",
                note="用户指定的视频号教育博主，先支持文本/转写内容蒸馏。",
            )
        creator_repository = SQLAlchemySocialCreatorRepository(session)
        creator_service = SocialCreatorService(creator_repository)
        if not await creator_repository.find_by_name("学习指导-亦木老师"):
            await creator_service.create_creator(
                name="学习指导-亦木老师",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                category=SocialCreatorCategory.GAOKAO,
                profile_url="",
                keywords=["高考", "升学", "志愿填报", "专业选择", "家长"],
            )
        news_repository = SQLAlchemyChangzhouNewsRepository(session)
        news_service = ChangzhouNewsService(news_repository)
        if not await news_repository.list():
            await news_service.create_news(
                title="常州教育局政策动态监控",
                category="政策文件",
                source_name="常州本地教育",
                url="",
                summary="用于持续收集招生政策、学区调整、考试安排等重大变化。",
            )
            await news_service.create_news(
                title="学校开放日与招生通知收集",
                category="校园公告",
                source_name="常州学校公开信息",
                url="",
                summary="跟踪开放日、招生说明会、校园活动和家长关注事项。",
            )
        await session.commit()


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
