from app.domain.material import Material, MaterialStatus
from app.repositories.material_repository import MaterialRepository
from app.services.material_service import MaterialNotFoundError

KEYWORDS = [
    "常州",
    "中考",
    "升学",
    "招生",
    "政策",
    "学校",
    "家长",
    "学区",
    "考试",
    "开放日",
    "高校",
    "专业",
    "就业",
    "录取",
]


def compact_text(text: str, limit: int = 180) -> str:
    compacted = " ".join(text.split())
    return compacted[:limit]


def infer_keywords(text: str, tags: list[str]) -> list[str]:
    found = [keyword for keyword in KEYWORDS if keyword in text]
    merged = [*tags, *found]
    result: list[str] = []
    for item in merged:
        if item and item not in result:
            result.append(item)
    return result[:10]


def infer_tags(material: Material, keywords: list[str]) -> list[str]:
    tags = [material.source.value, *(material.tags or [])]
    if material.source_name:
        tags.append(material.source_name)
    tags.extend(keywords[:4])
    result: list[str] = []
    for tag in tags:
        if tag and tag not in result:
            result.append(tag)
    return result[:8]


class MaterialProcessorService:
    def __init__(self, repository: MaterialRepository) -> None:
        self._repository = repository

    async def process(self, material_id: int) -> Material:
        material = await self._repository.get(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material not found: {material_id}")

        keywords = infer_keywords(material.content, material.tags)
        return await self._repository.update(
            material.update(
                summary=compact_text(material.content),
                tags=infer_tags(material, keywords),
                keywords=keywords,
                status=MaterialStatus.STORED,
            )
        )
