from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.sqlalchemy_material_repository import SQLAlchemyMaterialRepository
from app.schemas.material import MaterialResponse
from app.schemas.search import SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def build_search_service(session: DbSessionDep) -> SearchService:
    return SearchService(SQLAlchemyMaterialRepository(session))


SearchServiceDep = Annotated[SearchService, Depends(build_search_service)]


@router.get("", response_model=SearchResponse)
async def search_materials(
    service: SearchServiceDep,
    q: Annotated[str, Query(max_length=200)] = "",
) -> SearchResponse:
    items = await service.search(q)
    return SearchResponse(
        query=q,
        total=len(items),
        items=[MaterialResponse.model_validate(item) for item in items],
    )
