import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.domain.social_video import SocialVideoPlatform, SocialVideoScope

DISCOVERY_QUERIES = ["高考志愿填报", "强基计划", "综合评价", "高考选科", "专业选择"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerifiedVideo:
    title: str
    creator: str
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    original_url: str
    likes: int
    saves: int
    published_at: datetime
    play_url: str = ""


class VerifiedVideoProvider(Protocol):
    async def discover(self, queries: list[str]) -> list[VerifiedVideo]: ...


class DisabledVerifiedVideoProvider:
    async def discover(self, queries: list[str]) -> list[VerifiedVideo]:
        return []


HttpPost = Callable[
    [str, dict[str, str], dict[str, Any] | None, dict[str, Any] | None],
    Awaitable[dict[str, Any]],
]
HttpGet = Callable[[str, dict[str, str], dict[str, Any] | None], Awaitable[dict[str, Any]]]


async def default_http_post(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=json_body, params=params)
        response.raise_for_status()
        return response.json()


async def default_http_get(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


class TikHubDouyinVerifiedVideoProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        http_post: HttpPost = default_http_post,
        http_get: HttpGet = default_http_get,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http_post = http_post
        self._http_get = http_get

    async def discover(self, queries: list[str]) -> list[VerifiedVideo]:
        if not self._api_key:
            return []
        videos: list[VerifiedVideo] = []
        seen_urls: set[str] = set()
        for query in queries:
            for item in await self._discover_query(query):
                video = _to_verified_video(item)
                if video is None or video.original_url in seen_urls:
                    continue
                seen_urls.add(video.original_url)
                videos.append(video)
        return sorted(videos, key=lambda video: video.published_at, reverse=True)

    async def _discover_query(self, query: str) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            topics_payload = await self._http_post(
                f"{self._base_url}/api/v1/douyin/index/fetch_topic_suggest",
                headers,
                None,
                {"keyword": query},
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "tikhub_topic_suggest_failed",
                extra={"status_code": exc.response.status_code, "query": query},
            )
            return []

        items: list[dict[str, Any]] = []
        for topic in _extract_topics(topics_payload)[:3]:
            topic_id = str(topic.get("topic_id") or "").strip()
            if not topic_id:
                continue
            try:
                videos_payload = await self._http_get(
                    f"{self._base_url}/api/v1/douyin/app/v3/fetch_hashtag_video_list",
                    headers,
                    {"ch_id": topic_id},
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "tikhub_hashtag_video_list_failed",
                    extra={"status_code": exc.response.status_code, "query": query},
                )
                continue
            items.extend(_extract_items(videos_payload)[:20])
        return items


def build_verified_video_provider(settings: Settings) -> VerifiedVideoProvider:
    if settings.video_data_provider == "tikhub" and settings.tikhub_api_key:
        return TikHubDouyinVerifiedVideoProvider(
            api_key=settings.tikhub_api_key,
            base_url=settings.tikhub_base_url,
        )
    return DisabledVerifiedVideoProvider()


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", payload)
    for key in ("videos", "items", "aweme_list", "post_list", "data"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items:
                return items
    if isinstance(data, dict) and isinstance(data.get("mix_list"), list):
        items: list[dict[str, Any]] = []
        for row in data["mix_list"]:
            if not isinstance(row, dict):
                continue
            aweme = row.get("aweme_info")
            if isinstance(aweme, dict):
                items.append(aweme)
        return items
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _extract_topics(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", payload)
    if isinstance(data, dict) and isinstance(data.get("topic_list"), list):
        return [item for item in data["topic_list"] if isinstance(item, dict)]
    return []


def _to_verified_video(item: dict[str, Any]) -> VerifiedVideo | None:
    url = str(item.get("share_url") or item.get("url") or item.get("video_url") or "").strip()
    if not url.startswith("http"):
        aweme_id = str(item.get("aweme_id") or item.get("id") or "").strip()
        url = f"https://www.douyin.com/video/{aweme_id}" if aweme_id else ""
    title = str(item.get("desc") or item.get("title") or item.get("cha_name") or "").strip()
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    stats = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    creator = str(
        item.get("nickname")
        or item.get("author_name")
        or author.get("nickname")
        or ""
    ).strip()
    likes = _as_int(
        item.get("digg_count")
        or item.get("likes")
        or item.get("like_count")
        or stats.get("digg_count")
    )
    saves = _as_int(
        item.get("collect_count")
        or item.get("saves")
        or item.get("favorite_count")
        or stats.get("collect_count")
    )
    published_at = _published_at(item)
    play_url = _extract_play_url(item)
    if not title or not creator or not url:
        return None
    return VerifiedVideo(
        title=title,
        creator=creator,
        platform=SocialVideoPlatform.DOUYIN,
        scope=SocialVideoScope.NATIONAL_INFLUENCER,
        original_url=url,
        likes=likes,
        saves=saves,
        published_at=published_at,
        play_url=play_url,
    )


def _extract_play_url(item: dict[str, Any]) -> str:
    """Best-effort extraction of a downloadable video play URL from a TikHub item."""
    candidates: list[dict[str, Any]] = []

    def _collect(video: Any) -> None:
        if not isinstance(video, dict):
            return
        for key in ("play_addr", "play_addr_h264", "download_addr", "play_addr_h265"):
            addr = video.get(key)
            if isinstance(addr, dict):
                candidates.append(addr)

    _collect(item.get("video"))
    aweme = item.get("aweme_detail")
    if isinstance(aweme, dict):
        _collect(aweme.get("video"))

    # Some payloads wrap the real aweme under a different key.
    for wrapper in ("aweme_info", "aweme_detail", "video_info"):
        nested = item.get(wrapper)
        if isinstance(nested, dict):
            _collect(nested.get("video"))

    for addr in candidates:
        url_list = addr.get("url_list") if isinstance(addr.get("url_list"), list) else []
        for url in url_list:
            text = str(url).strip()
            if text.startswith("http"):
                return text
    return ""


def _as_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _published_at(item: dict[str, Any]) -> datetime:
    raw = item.get("create_time") or item.get("published_at")
    if isinstance(raw, int | float):
        return datetime.fromtimestamp(raw, tz=UTC)
    if isinstance(raw, str):
        with_z = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(with_z)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


def _date_string(*, days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).strftime("%Y%m%d")
