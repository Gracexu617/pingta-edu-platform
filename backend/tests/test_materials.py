import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_material(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/materials",
        json={
            "title": "龙城家长圈样本文章",
            "source": "公众号",
            "source_name": "龙城家长圈",
            "source_id": 1,
            "url": "https://mp.weixin.qq.com/",
            "tags": ["常州教育", "家长"],
            "summary": "",
            "content": "这是一条用于验证内容入库的数据。",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == "龙城家长圈样本文章"
    assert created["status"] == "待整理"
    assert created["summary"] == "这是一条用于验证内容入库的数据。"

    list_response = await client.get("/api/v1/materials")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_update_material_status(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/materials",
        json={
            "title": "待整理资料",
            "source": "教育资讯",
            "content": "资料正文。",
        },
    )

    material_id = create_response.json()["id"]
    update_response = await client.patch(
        f"/api/v1/materials/{material_id}",
        json={"status": "已入库", "tags": ["已整理"]},
    )

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "已入库"
    assert update_response.json()["tags"] == ["已整理"]


@pytest.mark.asyncio
async def test_update_missing_material_returns_404(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/materials/999", json={"status": "已入库"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_process_material_generates_summary_tags_and_keywords(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/materials",
        json={
            "title": "政策观察",
            "source": "教育资讯",
            "source_name": "常州教育资讯",
            "tags": ["原始标签"],
            "content": "常州家长关注中考政策、学校招生和升学安排。",
        },
    )
    material_id = create_response.json()["id"]

    process_response = await client.post(f"/api/v1/materials/{material_id}/process")

    assert process_response.status_code == 200
    body = process_response.json()
    assert body["status"] == "已入库"
    assert "常州" in body["keywords"]
    assert "中考" in body["keywords"]
    assert "教育资讯" in body["tags"]
