import os
from typing import List, Optional

from core.s3_client import s3, ensure_bucket_exists
from fastapi import UploadFile

from models.models import User


class FileService:

    async def save_file(self, file: UploadFile, username: str, logical_name: Optional[str] = None) -> dict:
        bucket_name = f"user-{username}"
        ensure_bucket_exists(bucket_name)

        file_key = file.filename
        s3.upload_fileobj(file.file, bucket_name, file_key)

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file.size
        }

    def get_file_info(self, file_name: str, username: str) -> Optional[dict]:
        file_path = self.get_file_path(file_name)
        if not os.path.exists(file_path):
            return None

        return {
            "filename": file_name,
            "size": os.path.getsize(file_path),
            "path": file_path
        }
