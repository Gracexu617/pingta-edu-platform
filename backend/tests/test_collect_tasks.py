import pytest
from httpx import AsyncClient

from app.services.content_fetcher import FetchedContent, HttpxContentFetcher


@pytest.mark.asyncio
async def test_create_list_and_update_collect_task(client: AsyncClient) -> None:
    create_response = await client.post("/api/v1/collect-tasks", json={"source_id": 1})

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["source_name"] == "龙城家长圈"
    assert created["status"] == "待采集"

    list_response = await client.get("/api/v1/collect-tasks")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == created["id"]

    update_response = await client.patch(
        f"/api/v1/collect-tasks/{created['id']}",
        json={"status": "处理中"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "处理中"


@pytest.mark.asyncio
async def test_create_collect_task_missing_source_returns_404(client: AsyncClient) -> None:
    response = await client.post("/api/v1/collect-tasks", json={"source_id": 999})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_missing_collect_task_returns_404(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/collect-tasks/999", json={"status": "已完成"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_execute_collect_task_creates_material(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch(
        self: HttpxContentFetcher,
        url: str,
        fallback_title: str,
    ) -> FetchedContent:
        return FetchedContent(
            title=f"{fallback_title}采集结果",
            content="抓取到的正文内容",
            tags=["网页采集"],
        )

    monkeypatch.setattr(HttpxContentFetcher, "fetch", fake_fetch)
    create_response = await client.post("/api/v1/collect-tasks", json={"source_id": 1})
    task_id = create_response.json()["id"]

    execute_response = await client.post(f"/api/v1/collect-tasks/{task_id}/execute")

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["task"]["status"] == "已完成"
    assert body["material"]["title"] == "龙城家长圈采集结果"
    assert body["material"]["content"] == "抓取到的正文内容"
