from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NewsImportance(StrEnum):
    NORMAL = "普通"
    IMPORTANT = "重要"
    URGENT = "重大"


@dataclass(frozen=True, slots=True)
class ChangzhouNews:
    id: int
    title: str
    category: str
    source_name: str
    url: str
    summary: str
    importance: NewsImportance
    published_at: datetime
    created_at: datetime
