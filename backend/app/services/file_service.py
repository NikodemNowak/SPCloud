import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core.s3_client import s3, ensure_bucket_exists
from fastapi import UploadFile, HTTPException, status
from models.models import User, FileStorage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from schemas.file import FileItem
from sqlalchemy.future import select


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_file(self, file: UploadFile, username: str, logical_name: Optional[str] = None) -> dict:
        existing_file_query = select(FileStorage).where(
            FileStorage.owner == username,
            FileStorage.name == file.filename
        )
        result = await self.db.execute(existing_file_query)
        existing_file = result.scalar_one_or_none()

        if existing_file:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File '{file.filename}' already exists. Please rename the file or delete the existing one first."
            )

        bucket_name = f"user-{username}"
        ensure_bucket_exists(bucket_name)

        file_key = file.filename
        try:
            s3.upload_fileobj(file.file, bucket_name, file_key)
        except Exception as e:
            raise ValueError(f"Failed to upload file: {str(e)}")

        new_file = FileStorage(
            id = uuid4(),
            path=f"s3://{bucket_name}/{file_key}",
            name=file.filename,
            size=file.size,
            owner=username,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        try:
            self.db.add(new_file)
            await self.db.commit()
            await self.db.refresh(new_file)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="File with the same name already exists in the database.",
            )
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file.size,
            "path": new_file.path
        }

    async def list_files(self, username: str) -> List[FileItem]:
         try:
             result = await self.db.execute(select(FileStorage).where(FileStorage.owner == username))
             files = result.scalars().all()
             return [FileItem.model_validate(file) for file in files]
         except Exception as e:
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail=f"Database error: {str(e)}",
             )
