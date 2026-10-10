from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TopicCreate(BaseModel):
    subject_id: int
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class TopicUpdate(BaseModel):
    subject_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class TopicPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
