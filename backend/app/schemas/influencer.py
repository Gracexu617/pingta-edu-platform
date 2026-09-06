from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.influencer import InfluencerPlatform


class InfluencerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    platform: InfluencerPlatform
    profile_url: str = Field(default="", max_length=500)
    note: str = ""


class InfluencerContentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    url: str = Field(default="", max_length=500)
    content: str = Field(min_length=1)


class InfluencerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    platform: InfluencerPlatform
    profile_url: str
    note: str
    core_views: list[str]
    style_traits: list[str]
    common_topics: list[str]
    parent_questions: list[str]
    content_count: int
    created_at: datetime
    updated_at: datetime


class InfluencerContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    influencer_id: int
    title: str
    url: str
    content: str
    summary: str
    created_at: datetime


class InfluencerListResponse(BaseModel):
    items: list[InfluencerResponse]


class InfluencerDistillResponse(BaseModel):
    influencer: InfluencerResponse
    content: InfluencerContentResponse
