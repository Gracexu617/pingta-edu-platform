import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_influencers_includes_yimu(client: AsyncClient) -> None:
    response = await client.get("/api/v1/influencers")

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "学习指导-亦木老师"
    assert response.json()["items"][0]["platform"] == "视频号"


@pytest.mark.asyncio
async def test_add_content_updates_influencer_profile(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/influencers/1/contents",
        json={
            "title": "升学建议",
            "content": "常州家长怎么选学校，要避开误区，关注中考政策和招生安排。",
        },
    )

    assert response.status_code == 200
    influencer = response.json()["influencer"]
    assert influencer["content_count"] == 1
    assert "中考" in influencer["core_views"]
    assert "误区" in influencer["style_traits"]
    assert "家长" in influencer["common_topics"]
    assert "怎么选" in influencer["parent_questions"]
