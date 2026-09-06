from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.source import SourceType


class CollectTaskStatus(StrEnum):
    PENDING = "待采集"
    PROCESSING = "处理中"
    DONE = "已完成"


@dataclass(frozen=True, slots=True)
class CollectTask:
    id: int
    source_id: int
    source_name: str
    source_type: SourceType
    url: str
    goal: str
    status: CollectTaskStatus
    created_at: datetime
    updated_at: datetime

    def update(self, *, status: CollectTaskStatus | None = None) -> "CollectTask":
        return replace(
            self,
            status=self.status if status is None else status,
            updated_at=datetime.now(UTC),
        )
