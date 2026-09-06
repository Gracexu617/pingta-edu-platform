from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.domain.social_creator import SocialCreator, SocialCreatorCategory
from app.domain.social_video import SocialVideoPlatform, SocialVideoScope
from app.repositories.sqlalchemy_social_creator_repository import SQLAlchemySocialCreatorRepository
from app.repositories.sqlalchemy_social_video_repository import SQLAlchemySocialVideoRepository
from app.services.social_video_service import (
    SocialVideoService,
    _classify_content,
    candidate_videos_for_creator,
    canonical_social_video_url_key,
    clean_video_transcript_text,
    matches_gaokao_discovery_scope,
    matches_topic,
)
from app.services.social_video_transcript_provider import TranscriptExtraction
from app.services.verified_video_provider import VerifiedVideo


class FakeVerifiedProvider:
    async def discover(self, keywords: list[str]) -> list[VerifiedVideo]:
        return [
            VerifiedVideo(
                title="高考强基计划怎么准备",
                creator="自动发现高考博主",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://www.douyin.com/video/987654321",
                likes=1300,
                saves=0,
                published_at=datetime.now(UTC),
            ),
            VerifiedVideo(
                title="未达标高考视频",
                creator="未达标博主",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://www.douyin.com/video/111111111",
                likes=10,
                saves=0,
                published_at=datetime.now(UTC),
            ),
            VerifiedVideo(
                title="职高专业怎么选",
                creator="中职升学博主",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://www.douyin.com/video/222222222",
                likes=5000,
                saves=1000,
                published_at=datetime.now(UTC),
            )
        ]


class FakeTranscriptProvider:
    async def extract(
        self,
        original_url: str,
        *,
        play_url: str = "",
    ) -> TranscriptExtraction | None:
        return TranscriptExtraction(
            text="大家好，嗯高考志愿填报先看分数。然后再看专业和城市。",
            source="TikHub字幕",
        )


@pytest.mark.asyncio
async def test_list_social_videos_returns_created_items(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/social-videos",
        json={
            "title": "真实抖音视频链接",
            "creator": "测试博主",
            "platform": "抖音",
            "scope": "全国大博主",
            "original_url": "https://www.douyin.com/video/123456789",
            "likes": 1250,
            "saves": 0,
        },
    )
    assert create_response.status_code == 201

    response = await client.get("/api/v1/social-videos")

    assert response.status_code == 200
    assert response.json()["items"][0]["original_url"] == "https://www.douyin.com/video/123456789"
    assert response.json()["items"][0]["transcript"] == ""


@pytest.mark.asyncio
async def test_create_social_video_evaluates_hot_threshold(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/social-videos",
        json={
            "title": "常州本地视频号真实链接样例",
            "creator": "学习指导-亦木老师",
            "platform": "微信视频号",
            "scope": "常州本地",
            "original_url": "https://channels.weixin.qq.com/example-video",
            "likes": 51,
            "saves": 10,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["is_hot"] is True
    assert data["threshold"] == "常州范围微信视频号：50赞或18收藏"


@pytest.mark.asyncio
async def test_update_hot_thresholds_recomputes_existing_videos(
    client: AsyncClient,
    tmp_path,
    monkeypatch,
) -> None:
    from app.services import hot_threshold_store

    monkeypatch.setattr(hot_threshold_store, "_PATH", tmp_path / "hot_thresholds.json")
    create_response = await client.post(
        "/api/v1/social-videos",
        json={
            "title": "高考志愿填报低互动视频",
            "creator": "测试博主",
            "platform": "抖音",
            "scope": "全国大博主",
            "original_url": "https://www.douyin.com/video/123123123",
            "likes": 100,
            "saves": 0,
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["is_hot"] is False

    update_response = await client.put(
        "/api/v1/social-videos/hot-thresholds",
        json={
            "items": [
                {"platform": "抖音", "scope": "全国大博主", "likes": 100, "saves": 50},
                {"platform": "微信视频号", "scope": "全国大博主", "likes": 250, "saves": 50},
                {"platform": "抖音", "scope": "常州本地", "likes": 125, "saves": 50},
                {"platform": "微信视频号", "scope": "常州本地", "likes": 50, "saves": 18},
            ]
        },
    )

    assert update_response.status_code == 200
    list_response = await client.get("/api/v1/social-videos")
    updated = next(
        item for item in list_response.json()["items"] if item["id"] == create_response.json()["id"]
    )
    assert updated["is_hot"] is True
    assert updated["threshold"] == "抖音大博主：100赞或50收藏"


@pytest.mark.asyncio
async def test_create_social_video_requires_real_url(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/social-videos",
        json={
            "title": "缺少真实链接",
            "creator": "测试账号",
            "platform": "抖音",
            "scope": "全国大博主",
            "original_url": "not-a-url",
            "likes": 1250,
            "saves": 0,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_collect_public_social_videos_is_idempotent(client: AsyncClient) -> None:
    first_response = await client.post("/api/v1/social-videos/collect-public")
    second_response = await client.post("/api/v1/social-videos/collect-public")

    assert first_response.status_code == 200
    assert first_response.json()["created"] == 0
    assert second_response.status_code == 200
    assert second_response.json()["created"] == 0


@pytest.mark.asyncio
async def test_collect_public_social_videos_auto_adds_discovered_creator(
    test_settings,
) -> None:
    from app.database import create_engine, create_session_factory, initialize_database

    engine = create_engine(test_settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine, session_factory, auto_create=True)
    async with session_factory() as session:
        service = SocialVideoService(
            SQLAlchemySocialVideoRepository(session),
            SQLAlchemySocialCreatorRepository(session),
            verified_video_provider=FakeVerifiedProvider(),
        )

        created = await service.collect_public_videos()
        await session.commit()

        creator = await SQLAlchemySocialCreatorRepository(session).find_by_name("自动发现高考博主")

    await engine.dispose()
    assert len(created) >= 1
    target = next(
        (video for video in created if video.original_url == "https://www.douyin.com/video/987654321"),
        None,
    )
    assert target is not None
    assert target.is_hot is True
    assert creator is not None
    assert creator.category == SocialCreatorCategory.GAOKAO


def test_matches_topic_requires_keyword_hit() -> None:
    assert matches_topic(title="高考志愿填报技巧", creator="升学博主", keywords=["高考"])
    assert not matches_topic(title="美食探店", creator="生活博主", keywords=["高考"])


def test_gaokao_discovery_scope_excludes_non_gaokao_tracks() -> None:
    assert matches_gaokao_discovery_scope(title="高考强基计划怎么准备", creator="升学博主")
    assert not matches_gaokao_discovery_scope(title="职高专业怎么选", creator="中职升学博主")
    assert not matches_gaokao_discovery_scope(title="AI专业选择指南", creator="留学博主")


def test_canonical_social_video_url_key_uses_douyin_video_id() -> None:
    first = "https://www.iesdouyin.com/share/video/7667472408277726458/?ts=1"
    second = "https://www.iesdouyin.com/share/video/7667472408277726458/?ts=2"

    assert canonical_social_video_url_key(first) == canonical_social_video_url_key(second)


def test_clean_video_transcript_text_removes_fillers_and_tags() -> None:
    cleaned = clean_video_transcript_text(
        "大家好，嗯这个高考志愿填报就是要先看分数。然后再看专业选择 #高考"
    )

    assert "大家好" not in cleaned
    assert "嗯" not in cleaned
    assert "就是" not in cleaned
    assert "#" not in cleaned
    assert "高考志愿填报" in cleaned


def test_clean_video_transcript_text_removes_more_fillers() -> None:
    cleaned = clean_video_transcript_text(
        "就是说嗯嗯这个高考志愿填报呢，对吧，简单来说就是要先看位次。"
    )

    assert "就是说" not in cleaned
    assert "嗯" not in cleaned
    assert "这个" not in cleaned
    assert "对吧" not in cleaned
    assert "简单来说" not in cleaned
    assert "高考志愿填报" in cleaned
    assert "位次" in cleaned


def test_classify_content_rejects_likely_background_lyrics() -> None:
    category, note = _classify_content(
        "风吹过远方，心还在等待。梦里的月光，照亮孤独的爱。"
        "青春不回来，眼泪落下来。"
    )

    assert category == "lyrics"
    assert "背景音乐歌词" in note


def test_classify_content_keeps_gaokao_speech() -> None:
    category, note = _classify_content(
        "高考志愿填报先看位次，再看专业对应的院校层次和就业方向。"
    )

    assert category == "valid"
    assert note == ""


@pytest.mark.asyncio
async def test_generate_social_video_transcript(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/social-videos",
        json={
            "title": "大家好，嗯高考志愿填报就是要先看分数 #高考",
            "creator": "测试博主",
            "platform": "抖音",
            "scope": "全国大博主",
            "original_url": "https://www.douyin.com/video/444444444",
            "likes": 1250,
            "saves": 0,
        },
    )
    video_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/social-videos/{video_id}/transcript")

    assert response.status_code == 200
    body = response.json()
    assert body["transcript_source"].startswith("未提取到视频内文字")
    assert body["transcript"] == ""


@pytest.mark.asyncio
async def test_generate_social_video_transcript_uses_provider_text(test_settings) -> None:
    from app.database import create_engine, create_session_factory, initialize_database
    from app.repositories.sqlalchemy_social_creator_repository import (
        SQLAlchemySocialCreatorRepository,
    )
    from app.repositories.sqlalchemy_social_video_repository import (
        SQLAlchemySocialVideoRepository,
    )

    engine = create_engine(test_settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine, session_factory, auto_create=True)
    async with session_factory() as session:
        service = SocialVideoService(
            SQLAlchemySocialVideoRepository(session),
            SQLAlchemySocialCreatorRepository(session),
            transcript_provider=FakeTranscriptProvider(),
        )
        video = await service.create_video(
            title="短标题",
            creator="测试博主",
            platform=SocialVideoPlatform.DOUYIN,
            scope=SocialVideoScope.NATIONAL_INFLUENCER,
            original_url="https://www.douyin.com/video/555555555",
            likes=1250,
            saves=0,
        )
        updated = await service.generate_transcript(video.id)

    await engine.dispose()
    assert updated is not None
    assert updated.transcript_source == "TikHub字幕"
    assert "大家好" not in updated.transcript
    assert "专业和城市" in updated.transcript


@pytest.mark.asyncio
async def test_generate_social_video_transcript_returns_404(client: AsyncClient) -> None:
    response = await client.post("/api/v1/social-videos/999/transcript")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_social_videos_returns_recommendation_score(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/social-videos",
        json={
            "title": "高考志愿填报普通视频",
            "creator": "测试博主",
            "platform": "抖音",
            "scope": "全国大博主",
            "original_url": "https://www.douyin.com/video/333333333",
            "likes": 1250,
            "saves": 0,
        },
    )

    response = await client.get("/api/v1/social-videos")

    assert response.status_code == 200
    assert response.json()["items"][0]["recommendation_score"] > 0


@pytest.mark.asyncio
async def test_collect_public_social_videos_writes_collection_log(
    client: AsyncClient,
    test_settings,
) -> None:
    from app.database import create_engine, create_session_factory, initialize_database
    from app.repositories.sqlalchemy_social_creator_repository import (
        SQLAlchemySocialCreatorRepository,
    )
    from app.repositories.sqlalchemy_social_video_repository import (
        SQLAlchemySocialVideoRepository,
    )

    engine = create_engine(test_settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine, session_factory, auto_create=True)
    async with session_factory() as session:
        service = SocialVideoService(
            SQLAlchemySocialVideoRepository(session),
            SQLAlchemySocialCreatorRepository(session),
            verified_video_provider=FakeVerifiedProvider(),
        )
        await service.collect_public_videos()

    await engine.dispose()
    logs_response = await client.get("/api/v1/social-videos/collection-logs")

    assert logs_response.status_code == 200
    assert logs_response.json()["items"][0]["discovered"] >= 3
    assert logs_response.json()["items"][0]["created"] >= 1


def test_candidate_videos_are_driven_by_creator_pool() -> None:
    now = datetime.now(UTC)
    creator = SocialCreator(
        id=1,
        name="学习指导-亦木老师",
        platform=SocialVideoPlatform.DOUYIN,
        scope=SocialVideoScope.NATIONAL_INFLUENCER,
        category=SocialCreatorCategory.GAOKAO,
        profile_url="",
        keywords=["高考"],
        enabled=True,
        created_at=now,
        updated_at=now,
    )

    candidates = candidate_videos_for_creator(creator)

    assert candidates[0]["creator"] == "学习指导-亦木老师"
    assert candidates[0]["platform"] == SocialVideoPlatform.DOUYIN
    assert candidates[0]["title"] == "高考志愿填报指导视频"
