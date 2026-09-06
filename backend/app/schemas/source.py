from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.source import SourceStatus, SourceType


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: SourceType
    url: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=500)


class SourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: SourceType | None = None
    url: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    status: SourceStatus | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: SourceType
    url: str
    note: str
    status: SourceStatus
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    items: list[SourceResponse]
