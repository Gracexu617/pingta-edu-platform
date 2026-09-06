from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.source import SourceType


class MaterialStatus(StrEnum):
    PENDING = "待整理"
    STORED = "已入库"


@dataclass(frozen=True, slots=True)
class Material:
    id: int
    title: str
    source: SourceType
    source_name: str | None
    source_id: int | None
    url: str
    tags: list[str]
    keywords: list[str]
    summary: str
    content: str
    status: MaterialStatus
    created_at: datetime
    updated_at: datetime

    def update(
        self,
        *,
        title: str | None = None,
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
        summary: str | None = None,
        content: str | None = None,
        status: MaterialStatus | None = None,
    ) -> "Material":
        return replace(
            self,
            title=self.title if title is None else title,
            tags=self.tags if tags is None else tags,
            keywords=self.keywords if keywords is None else keywords,
            summary=self.summary if summary is None else summary,
            content=self.content if content is None else content,
            status=self.status if status is None else status,
            updated_at=datetime.now(UTC),
        )
