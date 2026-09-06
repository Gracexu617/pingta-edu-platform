import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_materials_matches_content_and_tags(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/materials",
        json={
            "title": "常州升学资料",
            "source": "教育资讯",
            "tags": ["中考"],
            "keywords": ["政策"],
            "content": "常州家长关注学校招生。",
        },
    )

    response = await client.get("/api/v1/search", params={"q": "招生"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "常州升学资料"
