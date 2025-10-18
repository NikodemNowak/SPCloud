from datetime import datetime
from io import BytesIO
from typing import List, Optional
from uuid import uuid4

from core.s3_client import s3, ensure_bucket_exists
from fastapi import UploadFile, HTTPException, status
from models.models import User, FileStorage
from schemas.file import FileItem
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from util import _str_to_uuid


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
            id=uuid4(),
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

            if not files:
                return []

            return [FileItem.model_validate(file) for file in files]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}",
            )

    async def get_file(self, file_id: str, username: str):
        file_uuid = _str_to_uuid(file_id)

        result = await self.db.execute(
            select(FileStorage).where(
                FileStorage.id == file_uuid,
                FileStorage.owner == username
            )
        )
        file_record = result.scalar_one_or_none()

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or you don't have permission to access it"
            )

        bucket_name = f"user-{username}"
        file_key = file_record.name

        try:
            file_obj = BytesIO()
            s3.download_fileobj(bucket_name, file_key, file_obj)
            file_obj.seek(0)
            return file_obj, file_record.name
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to download file from S3: {str(e)}"
            )

    async def delete_file(self, file_id: str, username: str) -> dict:
        file_uuid = _str_to_uuid(file_id)

        result = await self.db.execute(
            select(FileStorage).where(
                FileStorage.id == file_uuid,
                FileStorage.owner == username
            )
        )
        file_record = result.scalar_one_or_none()

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or you don't have permission to delete it"
            )

        bucket_name = f"user-{username}"
        file_key = file_record.name

        try:
            s3.delete_object(Bucket=bucket_name, Key=file_key)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file from S3: {str(e)}"
            )

        try:
            await self.db.delete(file_record)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file from database: {str(e)}"
            )

        return {"message": f"File '{file_record.name}' deleted successfully"}
