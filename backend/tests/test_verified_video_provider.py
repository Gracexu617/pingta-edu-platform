from typing import Any

import httpx
import pytest

from app.services.verified_video_provider import TikHubDouyinVerifiedVideoProvider


@pytest.mark.asyncio
async def test_tikhub_provider_uses_topic_suggest_and_parses_hashtag_videos() -> None:
    calls: list[dict[str, Any]] = []

    async def fake_post(
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        calls.append(
            {
                "method": "POST",
                "url": url,
                "headers": headers,
                "json": json_body,
                "params": params,
            }
        )
        return {
            "data": {
                "topic_list": [
                    {
                        "topic_id": "topic-1",
                        "topic_name": "高考志愿填报",
                    }
                ]
            }
        }

    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        calls.append({"method": "GET", "url": url, "headers": headers, "params": params})
        return {
            "data": {
                "aweme_list": [],
                "mix_list": [
                    {
                        "aweme_info": {
                            "aweme_id": "123",
                            "desc": "高考志愿填报技巧",
                            "author": {"nickname": "升学老师"},
                            "statistics": {"digg_count": 1300, "collect_count": 600},
                            "create_time": 1782864000,
                        }
                    }
                ]
            }
        }

    provider = TikHubDouyinVerifiedVideoProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        http_post=fake_post,
        http_get=fake_get,
    )

    videos = await provider.discover(["高考志愿填报"])

    assert calls[0]["url"].endswith("/api/v1/douyin/index/fetch_topic_suggest")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["params"]["keyword"] == "高考志愿填报"
    assert calls[1]["url"].endswith("/api/v1/douyin/app/v3/fetch_hashtag_video_list")
    assert calls[1]["params"]["ch_id"] == "topic-1"
    assert videos[0].likes == 1300
    assert videos[0].saves == 600
    assert videos[0].original_url == "https://www.douyin.com/video/123"


@pytest.mark.asyncio
async def test_tikhub_provider_skips_forbidden_topic_suggest() -> None:
    async def fake_post(
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = httpx.Request("POST", url)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    provider = TikHubDouyinVerifiedVideoProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        http_post=fake_post,
    )

    assert await provider.discover(["高考志愿填报"]) == []
