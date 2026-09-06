from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.domain.changzhou_news import ChangzhouNews, NewsImportance
from app.services.changzhou_news_collector import (
    canonical_news_title_key,
    gaokao_relevance_score,
    is_gaokao_admission_related,
)
from app.services.changzhou_news_service import ChangzhouNewsService


@pytest.mark.asyncio
async def test_list_changzhou_news_contains_seed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/changzhou-news")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"]


@pytest.mark.asyncio
async def test_create_changzhou_news_classifies_importance(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/changzhou-news",
        json={
            "title": "常州某片区学区调整",
            "category": "学区",
            "source_name": "本地媒体",
            "summary": "涉及学区调整和招生政策。",
        },
    )

    assert response.status_code == 201
    assert response.json()["importance"] == "重大"


def test_changzhou_news_focuses_on_gaokao_admission() -> None:
    assert is_gaokao_admission_related("常州高考志愿填报政策发布，涉及本科录取位次")
    assert is_gaokao_admission_related("常州高三二模分数线与强基计划报名提醒")
    assert is_gaokao_admission_related("全国高校本科招生简章发布，包含选科要求和招生计划")
    assert is_gaokao_admission_related("中外合作办学高校招生项目更新，面向江苏考生")
    assert is_gaokao_admission_related("综合评价招生报名启动，重点说明院校专业组和录取规则")
    assert not is_gaokao_admission_related("市教育局组织直属单位安保人员开展反恐培训")
    assert not is_gaokao_admission_related("上海10区公示中小学食堂供餐服务招标结果")


def test_gaokao_relevance_score_penalizes_noise() -> None:
    focused = gaokao_relevance_score("常州高考招生录取分数线和志愿填报提醒")
    university_admission = gaokao_relevance_score("全国高校本科招生简章和中外合作办学项目汇总")
    noisy = gaokao_relevance_score("常州学校食堂供餐服务和安保培训会议")

    assert focused > 30
    assert university_admission > 30
    assert noisy < 0


def test_canonical_news_title_key_collapses_noisy_duplicates() -> None:
    assert canonical_news_title_key("【常州】高考志愿填报政策发布1") == canonical_news_title_key(
        "常州高考志愿填报政策发布"
    )


@pytest.mark.asyncio
async def test_list_changzhou_news_deduplicates_existing_rows() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)

    class FakeRepository:
        async def list(self) -> list[ChangzhouNews]:
            return [
                ChangzhouNews(
                    id=1,
                    title="常州高考志愿填报政策发布",
                    category="高考",
                    source_name="常州市教育局",
                    url="https://example.com/news",
                    summary="第一条",
                    importance=NewsImportance.URGENT,
                    published_at=now,
                    created_at=now,
                ),
                ChangzhouNews(
                    id=2,
                    title="【常州】高考志愿填报政策发布1",
                    category="高考",
                    source_name="微信公众号",
                    url="https://mirror.example.com/news",
                    summary="重复条",
                    importance=NewsImportance.URGENT,
                    published_at=now,
                    created_at=now,
                ),
            ]

        async def create(self, news: ChangzhouNews) -> ChangzhouNews:
            return news

        async def exists_by_url(self, url: str) -> bool:
            return False

    service = ChangzhouNewsService(FakeRepository())

    assert [item.id for item in await service.list_news()] == [1]
