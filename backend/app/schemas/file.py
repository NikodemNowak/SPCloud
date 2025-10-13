from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FileItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    path: str
    size: int
    owner: str
    current_version: int
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
