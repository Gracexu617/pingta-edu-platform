from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.material import MaterialStatus
from app.domain.source import SourceType


class MaterialCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    source: SourceType
    source_name: str | None = Field(default=None, max_length=120)
    source_id: int | None = None
    url: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    summary: str = ""
    content: str = Field(min_length=1)


class MaterialUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    tags: list[str] | None = None
    keywords: list[str] | None = None
    summary: str | None = None
    content: str | None = None
    status: MaterialStatus | None = None


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class MaterialListResponse(BaseModel):
    items: list[MaterialResponse]
