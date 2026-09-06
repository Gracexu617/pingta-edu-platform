from typing import Protocol

from app.domain.social_video import SocialVideo


class SocialVideoRepository(Protocol):
    async def list(self) -> list[SocialVideo]: ...

    async def find_by_id(self, video_id: int) -> SocialVideo | None: ...

    async def find_by_url(self, url: str) -> SocialVideo | None: ...

    async def create(self, item: SocialVideo) -> SocialVideo: ...

    async def update_transcript(
        self,
        video_id: int,
        *,
        transcript: str,
        transcript_source: str,
        manuscript: str = "",
    ) -> SocialVideo | None: ...

    async def update_manuscript(
        self,
        video_id: int,
        manuscript: str,
    ) -> SocialVideo | None: ...

    async def update_play_url(
        self,
        video_id: int,
        *,
        play_url: str,
    ) -> SocialVideo | None: ...

    async def update_hot_flags(
        self,
        video_id: int,
        *,
        is_hot: bool,
        threshold: str,
        reason: str,
    ) -> SocialVideo | None: ...
