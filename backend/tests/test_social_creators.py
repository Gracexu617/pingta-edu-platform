import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_social_creators_contains_default_creator(client: AsyncClient) -> None:
    response = await client.get("/api/v1/social-creators")

    assert response.status_code == 200
    creators = response.json()["items"]
    default_creator = next(item for item in creators if item["name"] == "学习指导-亦木老师")
    assert default_creator["category"] == "高考升学"
    assert "高考" in default_creator["keywords"]


@pytest.mark.asyncio
async def test_create_social_creator_for_gaokao_pool(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/social-creators",
        json={
            "name": "高考升学博主样本",
            "platform": "抖音",
            "scope": "全国大博主",
            "category": "高考升学",
            "profile_url": "",
            "keywords": ["高考", "志愿填报"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "高考升学"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_update_social_creator_keywords_and_enabled_status(client: AsyncClient) -> None:
    list_response = await client.get("/api/v1/social-creators")
    creator = next(
        item for item in list_response.json()["items"] if item["name"] == "学习指导-亦木老师"
    )

    response = await client.patch(
        f"/api/v1/social-creators/{creator['id']}",
        json={"keywords": ["高考", "强基计划"], "enabled": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == ["高考", "强基计划"]
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_public_collection_requires_verified_video_provider(
    client: AsyncClient,
) -> None:
    list_response = await client.get("/api/v1/social-creators")
    creator = next(
        item for item in list_response.json()["items"] if item["name"] == "学习指导-亦木老师"
    )
    await client.patch(f"/api/v1/social-creators/{creator['id']}", json={"enabled": False})

    response = await client.post("/api/v1/social-videos/collect-public")
    videos_response = await client.get("/api/v1/social-videos")

    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert videos_response.json()["items"] == []
