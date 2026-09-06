from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.changzhou_news import NewsImportance


class ChangzhouNewsCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    category: str = Field(default="本地教育", max_length=60)
    source_name: str = Field(default="手动录入", max_length=120)
    url: str = Field(default="", max_length=500)
    summary: str = ""
    published_at: datetime | None = None


class ChangzhouNewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    source_name: str
    url: str
    summary: str
    importance: NewsImportance
    published_at: datetime
    created_at: datetime


class ChangzhouNewsListResponse(BaseModel):
    items: list[ChangzhouNewsResponse]


class ChangzhouNewsCollectResponse(BaseModel):
    discovered: int
    duplicate_skipped: int
    created: int
    items: list[ChangzhouNewsResponse]
