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


class FileSetIsFavorite(BaseModel):
    file_id: str
    is_favorite: bool


class FileDownloadManyFiles(BaseModel):
    file_ids: list[str]


class StorageInfo(BaseModel):
    """Schema for user storage information"""
    username: str
    total_files: int
    total_size_bytes: int
    total_size_mb: float
    max_storage_mb: int
    used_storage_mb: float
    available_storage_mb: float
    storage_usage_percentage: float
    total_favorite_files: int
    total_versions: int
    total_versions_size_bytes: int
    total_versions_size_mb: float


