from pydantic import BaseModel

from app.schemas.material import MaterialResponse


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[MaterialResponse]
