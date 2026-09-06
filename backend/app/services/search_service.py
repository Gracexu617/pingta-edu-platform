from app.domain.material import Material
from app.repositories.material_repository import MaterialRepository


class SearchService:
    def __init__(self, repository: MaterialRepository) -> None:
        self._repository = repository

    async def search(self, query: str) -> list[Material]:
        key = query.strip().lower()
        if not key:
            return await self._repository.list()
        items = await self._repository.list()
        return [
            item
            for item in items
            if key
            in " ".join(
                [
                    item.title,
                    item.summary,
                    item.content,
                    " ".join(item.tags),
                    " ".join(item.keywords),
                ]
            ).lower()
        ]
