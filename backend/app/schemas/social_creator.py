from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.social_creator import SocialCreatorCategory
from app.domain.social_video import SocialVideoPlatform, SocialVideoScope


class SocialCreatorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    category: SocialCreatorCategory
    profile_url: str = Field(default="", max_length=800)
    keywords: list[str] = Field(default_factory=list)


class SocialCreatorUpdateRequest(BaseModel):
    platform: SocialVideoPlatform | None = None
    scope: SocialVideoScope | None = None
    category: SocialCreatorCategory | None = None
    profile_url: str | None = Field(default=None, max_length=800)
    keywords: list[str] | None = None
    enabled: bool | None = None


class SocialCreatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    category: SocialCreatorCategory
    profile_url: str
    keywords: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SocialCreatorListResponse(BaseModel):
    items: list[SocialCreatorResponse]
