from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import Settings
from app.domain.changzhou_news import ChangzhouNews, NewsImportance
from app.repositories.changzhou_news_repository import ChangzhouNewsRepository
from app.services.changzhou_news_collector import (
    RawNewsItem,
    canonical_news_title_key,
    normalize_url,
    run_collection,
)


def classify_importance(text: str) -> NewsImportance:
    if any(word in text for word in ["学区调整", "招生政策", "录取", "考试安排"]):
        return NewsImportance.URGENT
    if any(word in text for word in ["开放日", "竞赛", "通知", "排名"]):
        return NewsImportance.IMPORTANT
    return NewsImportance.NORMAL


@dataclass
class CollectResult:
    discovered: int
    duplicate_skipped: int
    created: int
    items: list[ChangzhouNews]


class ChangzhouNewsService:
    def __init__(self, repository: ChangzhouNewsRepository) -> None:
        self._repository = repository

    async def list_news(self) -> list[ChangzhouNews]:
        return _dedupe_news(await self._repository.list())

    async def create_news(
        self,
        *,
        title: str,
        category: str,
        source_name: str,
        url: str,
        summary: str,
        published_at: datetime | None = None,
    ) -> ChangzhouNews:
        text = f"{title} {summary} {category}"
        now = datetime.now(UTC)
        return await self._repository.create(
            ChangzhouNews(
                id=0,
                title=title.strip(),
                category=category.strip() or "本地教育",
                source_name=source_name.strip() or "手动录入",
                url=normalize_url(url.strip()) if url else "",
                summary=summary.strip(),
                importance=classify_importance(text),
                published_at=published_at or now,
                created_at=now,
            )
        )

    async def collect_news(self, settings: Settings) -> CollectResult:
        """跑采集器拿到原始条目，按 URL + 标题指纹去重后入库。"""
        raw: list[RawNewsItem] = await run_collection(settings)
        created: list[ChangzhouNews] = []
        duplicate_skipped = 0
        now = datetime.now(UTC)
        existing = await self._repository.list()
        existing_urls = {normalize_url(news.url) for news in existing if news.url}
        existing_title_keys = {
            canonical_news_title_key(news.title)
            for news in existing
            if canonical_news_title_key(news.title)
        }
        for item in raw:
            norm_url = normalize_url(item.url.strip()) if item.url else ""
            title_key = canonical_news_title_key(item.title)
            if (norm_url and norm_url in existing_urls) or (
                title_key and title_key in existing_title_keys
            ):
                duplicate_skipped += 1
                continue
            news = await self._repository.create(
                ChangzhouNews(
                    id=0,
                    title=item.title.strip(),
                    category=item.category or "媒体",
                    source_name=item.source_name.strip() or "自动采集",
                    url=norm_url,
                    summary=item.summary.strip(),
                    importance=classify_importance(f"{item.title} {item.summary} {item.category}"),
                    published_at=item.published_at or now,
                    created_at=now,
                )
            )
            created.append(news)
            if norm_url:
                existing_urls.add(norm_url)
            if title_key:
                existing_title_keys.add(title_key)
        return CollectResult(
            discovered=len(raw),
            duplicate_skipped=duplicate_skipped,
            created=len(created),
            items=created,
        )


def _dedupe_news(items: list[ChangzhouNews]) -> list[ChangzhouNews]:
    seen_urls: set[str] = set()
    seen_title_keys: set[str] = set()
    deduped: list[ChangzhouNews] = []
    for item in items:
        key_url = normalize_url(item.url) if item.url else ""
        key_title = canonical_news_title_key(item.title)
        if key_url and key_url in seen_urls:
            continue
        if key_title and key_title in seen_title_keys:
            continue
        if key_url:
            seen_urls.add(key_url)
        if key_title:
            seen_title_keys.add(key_title)
        deduped.append(item)
    return deduped
