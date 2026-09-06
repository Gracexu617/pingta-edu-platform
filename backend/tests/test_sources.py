import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_sources_includes_configured_wechat_account(client: AsyncClient) -> None:
    response = await client.get("/api/v1/sources")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["name"] == "龙城家长圈"
    assert items[0]["type"] == "公众号"
    assert items[0]["status"] == "启用"


@pytest.mark.asyncio
async def test_create_source(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/sources",
        json={
            "name": "常州教育发布",
            "type": "公众号",
            "url": "https://mp.weixin.qq.com/",
            "note": "教育局公开信息。",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 3
    assert body["name"] == "常州教育发布"
    assert body["status"] == "启用"


@pytest.mark.asyncio
async def test_create_source_rejects_duplicate_name(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/sources",
        json={
            "name": "龙城家长圈",
            "type": "公众号",
            "url": "https://mp.weixin.qq.com/",
            "note": "",
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_source_status(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/sources/1", json={"status": "暂停"})

    assert response.status_code == 200
    assert response.json()["status"] == "暂停"


@pytest.mark.asyncio
async def test_update_missing_source_returns_404(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/sources/999", json={"status": "暂停"})

    assert response.status_code == 404
