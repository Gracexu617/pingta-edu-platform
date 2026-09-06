from typing import Protocol

from app.domain.changzhou_news import ChangzhouNews


class ChangzhouNewsRepository(Protocol):
    async def list(self) -> list[ChangzhouNews]: ...

    async def create(self, item: ChangzhouNews) -> ChangzhouNews: ...

    async def exists_by_url(self, url: str) -> bool: ...
