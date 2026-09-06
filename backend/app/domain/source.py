from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class SourceType(StrEnum):
    WECHAT_OFFICIAL = "公众号"
    WECHAT_CHANNELS = "视频号"
    UNIVERSITY_SITE = "高校官网"
    EDUCATION_NEWS = "教育资讯"
    MANUAL = "手动资料"


class SourceStatus(StrEnum):
    ENABLED = "启用"
    PAUSED = "暂停"


@dataclass(frozen=True, slots=True)
class Source:
    id: int
    name: str
    type: SourceType
    url: str
    note: str
    status: SourceStatus
    created_at: datetime
    updated_at: datetime

    def update(
        self,
        *,
        name: str | None = None,
        type: SourceType | None = None,
        url: str | None = None,
        note: str | None = None,
        status: SourceStatus | None = None,
    ) -> "Source":
        return replace(
            self,
            name=self.name if name is None else name,
            type=self.type if type is None else type,
            url=self.url if url is None else url,
            note=self.note if note is None else note,
            status=self.status if status is None else status,
            updated_at=datetime.now(UTC),
        )
