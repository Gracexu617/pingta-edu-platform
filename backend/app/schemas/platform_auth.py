from pydantic import BaseModel


class ProviderAuthStatus(BaseModel):
    provider: str
    configured: bool
    oauth_ready: bool
    note: str


class PlatformAuthStatusResponse(BaseModel):
    providers: list[ProviderAuthStatus]
