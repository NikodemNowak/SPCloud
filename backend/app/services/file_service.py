import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import List
from uuid import uuid4

from core.s3_client import s3, ensure_bucket_exists
from fastapi import UploadFile, HTTPException, status
from models.models import User, FileStorage
from schemas.file import FileItem, FileSetIsFavorite
from services.log_service import LogService, LogAction
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from util import _str_to_uuid


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.log_service = LogService(db)

    async def upload_file(self, file: UploadFile, username: str, ip_address: str = None) -> dict:
        try:
            result = await self.db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

            if (user.used_storage_mb + file.size / (1024 * 1024)) > user.max_storage_mb:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploading this file would exceed your storage quota."
                )

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

            file_content = await file.read()
            file_size = len(file_content)
            await file.seek(0)

            try:
                s3.upload_fileobj(BytesIO(file_content), bucket_name, file_key)
            except Exception as e:
                raise ValueError(f"Failed to upload file: {str(e)}")

            new_file = FileStorage(
                id=uuid4(),
                path=f"s3://{bucket_name}/{file_key}",
                name=file.filename,
                size=file.size,
                owner=username,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
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
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {str(e)}",
                )

            user.used_storage_mb += file_size / (1024 * 1024)
            try:
                self.db.add(user)
                await self.db.commit()
                await self.db.refresh(user)
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update user storage usage: {str(e)}",
                )

            await self.log_service.log_action(
                action=LogAction.FILE_UPLOAD,
                username=username,
                status="SUCCESS",
                file_id=new_file.id,
                details={
                    "size": new_file.size,
                    "path": new_file.path,
                    "ip_address": ip_address
                }
            )

            return {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": file_size,
                "path": new_file.path
            }
        except Exception as e:
            await self.log_service.log_action(
                action=LogAction.FILE_UPLOAD,
                username=username,
                status="FAILED",
                details={
                    "error": str(e),
                    "ip_address": ip_address
                },
            )
            raise

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

    async def download_file(self, file_id: str, username: str, ip_address: str = None):
        try:
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

                await self.log_service.log_action(
                    action=LogAction.FILE_DOWNLOAD,
                    username=username,
                    status="SUCCESS",
                    file_id=file_record.id,
                    details={
                        "size": file_record.size,
                        "ip_address": ip_address
                    }
                )

                return file_obj, file_record.name
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download file from S3: {str(e)}"
                )
        except Exception as e:
            await self.log_service.log_action(
                action=LogAction.FILE_DOWNLOAD,
                username=username,
                status="FAILED",
                file_id=file_id,
                details={
                    "error": str(e),
                    "ip_address": ip_address
                }
            )
            raise

    async def get_many_files(self, file_ids: List[str], username: str, ip_address: str = None):
        try:
            zip_buffer = BytesIO()
            size = 0.0
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for file_id in file_ids:
                    file_uuid = _str_to_uuid(file_id)

                    result = await self.db.execute(
                        select(FileStorage).where(
                            FileStorage.id == file_uuid,
                            FileStorage.owner == username
                        )
                    )
                    file_record = result.scalar_one_or_none()

                    if not file_record:
                        continue

                    size += file_record.size

                    bucket_name = f"user-{username}"
                    file_key = file_record.name

                    try:
                        file_obj = BytesIO()
                        s3.download_fileobj(bucket_name, file_key, file_obj)
                        file_obj.seek(0)
                        zip_file.writestr(file_record.name, file_obj.read())
                    except Exception as e:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to download file '{file_record.name}' from S3: {str(e)}"
                        )

            zip_buffer.seek(0)
            zip_filename = "files_bundle.zip"

            await self.log_service.log_action(
                action=LogAction.FILE_MANY_DOWNLOAD,
                username=username,
                status="SUCCESS",
                file_id=",".join(file_ids),
                details={
                    "ip_address": ip_address,
                    "total_size_bytes": size,
                    "files_count": len(file_ids)
                }
            )

            return zip_buffer, zip_filename
        except Exception as e:
            await self.log_service.log_action(
                action=LogAction.FILE_MANY_DOWNLOAD,
                username=username,
                status="FAILED",
                file_id=",".join(file_ids),
                details={
                    "error": str(e),
                    "ip_address": ip_address
                }
            )
            raise

    async def delete_file(self, file_id: str, username: str, ip_address: str = None) -> dict:
        try:
            file_uuid = _str_to_uuid(file_id)

            result = await self.db.execute(
                select(FileStorage).where(
                    FileStorage.id == file_uuid,
                    FileStorage.owner == username
                )
            )
            file_record = result.scalar_one_or_none()

            result = await self.db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

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
                user.used_storage_mb -= file_record.size / (1024 * 1024)
                if user.used_storage_mb < 0:
                    user.used_storage_mb = 0
                self.db.add(user)
                await self.db.commit()
                await self.db.refresh(user)
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update user storage usage: {str(e)}"
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

            await self.log_service.log_action(
                action=LogAction.FILE_DELETE,
                username=username,
                status="SUCCESS",
                file_id=file_record.id,
                details={
                    "size": file_record.size,
                    "versions_count": len(file_record.versions),
                    "ip_address": ip_address
                }
            )

            return {"message": f"File '{file_record.name}' deleted successfully"}
        except Exception as e:
            await self.log_service.log_action(
                action=LogAction.FILE_DELETE,
                username=username,
                status="FAILED",
                file_id=file_id,
                details={
                    "error": str(e),
                    "ip_address": ip_address
                }
            )
            raise

    async def set_favorite_file(self, file_id: str, is_favorite: bool, username: str, ip_address: str = None) -> dict:
        try:
            result = await self.db.execute(
                select(FileStorage).where(
                    FileStorage.id == file_id,
                    FileStorage.owner == username
                )
            )
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found or you don't have permission to modify it"
                )

            file_record.is_favorite = is_favorite
            file_record.updated_at = datetime.now(timezone.utc)

            try:
                self.db.add(file_record)
                await self.db.commit()
                await self.db.refresh(file_record)
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update file in database: {str(e)}"
                )

            action = LogAction.FILE_FAVORITE if is_favorite else LogAction.FILE_UNFAVORITE

            await self.log_service.log_action(
                action=action,
                username=username,
                status="SUCCESS",
                file_id=file_record.id,
                details={
                    "ip_address": ip_address
                }
            )

            return {"file_id": str(file_record.id), "is_favorite": file_record.is_favorite}
        except Exception as e:
            await self.log_service.log_action(
                action=LogAction.FILE_FAVORITE if is_favorite else LogAction.FILE_UNFAVORITE,
                username=username,
                status="FAILED",
                file_id=file_id,
                details={
                    "error": str(e),
                    "ip_address": ip_address
                }
            )
            raise
