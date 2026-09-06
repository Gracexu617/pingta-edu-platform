from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.domain.source import Source, SourceStatus, SourceType


class SourceRepository(Protocol):
    async def list(self) -> list[Source]: ...

    async def get(self, source_id: int) -> Source | None: ...

    async def find_by_name(self, name: str) -> Source | None: ...

    async def create(self, source: Source) -> Source: ...

    async def update(self, source: Source) -> Source: ...


def default_sources() -> list[Source]:
    now = datetime.now(UTC)
    return [
        Source(
            id=1,
            name="龙城家长圈",
            type=SourceType.WECHAT_OFFICIAL,
            url="https://mp.weixin.qq.com/",
            note="用户指定的首批微信公众号来源，后续接入合规采集方案。",
            status=SourceStatus.ENABLED,
            created_at=now,
            updated_at=now,
        ),
        Source(
            id=2,
            name="常州教育资讯",
            type=SourceType.EDUCATION_NEWS,
            url="https://example.com/changzhou-education",
            note="本地政策、升学、学校动态。",
            status=SourceStatus.ENABLED,
            created_at=now,
            updated_at=now,
        ),
    ]


class InMemorySourceRepository:
    """Small repository used before PostgreSQL is introduced."""

    def __init__(self, initial_sources: Iterable[Source] | None = None) -> None:
        self._lock = Lock()
        self._sources = {source.id: deepcopy(source) for source in (initial_sources or [])}
        self._next_id = max(self._sources.keys(), default=0) + 1

    async def list(self) -> list[Source]:
        with self._lock:
            return sorted(
                (deepcopy(source) for source in self._sources.values()),
                key=lambda item: item.id,
            )

    async def get(self, source_id: int) -> Source | None:
        with self._lock:
            source = self._sources.get(source_id)
            return deepcopy(source) if source else None

    async def find_by_name(self, name: str) -> Source | None:
        normalized = name.strip().casefold()
        with self._lock:
            for source in self._sources.values():
                if source.name.casefold() == normalized:
                    return deepcopy(source)
        return None

    async def create(self, source: Source) -> Source:
        with self._lock:
            source_id = self._next_id
            self._next_id += 1
            stored = deepcopy(source)
            stored = Source(
                id=source_id,
                name=stored.name,
                type=stored.type,
                url=stored.url,
                note=stored.note,
                status=stored.status,
                created_at=stored.created_at,
                updated_at=stored.updated_at,
            )
            self._sources[source_id] = stored
            return deepcopy(stored)

    async def update(self, source: Source) -> Source:
        with self._lock:
            self._sources[source.id] = deepcopy(source)
            return deepcopy(source)
