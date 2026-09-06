from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.collect_task import CollectTaskStatus
from app.domain.source import SourceType
from app.schemas.material import MaterialResponse


class CollectTaskCreateRequest(BaseModel):
    source_id: int


class CollectTaskUpdateRequest(BaseModel):
    status: CollectTaskStatus


class CollectTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str
    source_type: SourceType
    url: str
    goal: str
    status: CollectTaskStatus
    created_at: datetime
    updated_at: datetime


class CollectTaskListResponse(BaseModel):
    items: list[CollectTaskResponse]


class CollectTaskExecuteResponse(BaseModel):
    task: CollectTaskResponse
    material: MaterialResponse
