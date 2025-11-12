import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import List
from uuid import uuid4
import os

from core.s3_client import s3, ensure_bucket_exists
from fastapi import UploadFile, HTTPException, status
from models.models import User, FileStorage, FileVersion
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

    def _build_versioned_filename(self, original_filename: str, version_number: int) -> str:
        """
        Tworzy nazwę pliku z numerem wersji: filename_v1.txt
        """
        name, ext = os.path.splitext(original_filename)
        return f"{name}_v{version_number}{ext}"

    def _parse_base_filename(self, filename: str) -> str:
        """
        Parsuje nazwę pliku i zwraca bazową nazwę bez wersji
        Np. 'document_v1.txt' -> 'document.txt'
        """
        name, ext = os.path.splitext(filename)
        # Usuń _vN jeśli istnieje
        if '_v' in name:
            parts = name.rsplit('_v', 1)
            if len(parts) == 2 and parts[1].isdigit():
                return f"{parts[0]}{ext}"
        return filename

    async def upload_file(self, file: UploadFile, username: str, ip_address: str = None) -> dict:
        try:
            result = await self.db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

            file_content = await file.read()
            file_size = len(file_content)

            if (user.used_storage_mb + file_size / (1024 * 1024)) > user.max_storage_mb:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploading this file would exceed your storage quota."
                )

            # Sprawdź czy plik o tej nazwie już istnieje
            base_filename = self._parse_base_filename(file.filename)
            existing_file_query = select(FileStorage).where(
                FileStorage.owner == username,
                FileStorage.name == base_filename
            )
            result = await self.db.execute(existing_file_query)
            existing_file = result.scalar_one_or_none()

            bucket_name = f"user-{username}"
            ensure_bucket_exists(bucket_name)

            if existing_file:
                # Plik istnieje - tworzymy nową wersję
                # Znajdź najwyższy numer wersji
                versions_query = select(FileVersion).where(
                    FileVersion.file_id == existing_file.id
                ).order_by(FileVersion.version_number.desc())
                result = await self.db.execute(versions_query)
                versions = result.scalars().all()

                new_version_number = max([v.version_number for v in versions]) + 1 if versions else existing_file.current_version + 1

                # Utwórz nazwę pliku z wersją
                versioned_filename = self._build_versioned_filename(base_filename, new_version_number)
                file_key = versioned_filename

                # Upload do S3
                try:
                    s3.upload_fileobj(BytesIO(file_content), bucket_name, file_key)
                except Exception as e:
                    raise ValueError(f"Failed to upload file: {str(e)}")

                # Utwórz nową wersję w bazie
                new_version = FileVersion(
                    id=uuid4(),
                    file_id=existing_file.id,
                    version_number=new_version_number,
                    path=f"s3://{bucket_name}/{file_key}",
                    size=file_size,
                    created_at=datetime.now(timezone.utc),
                    created_by=username
                )

                try:
                    self.db.add(new_version)

                    # Zaktualizuj current_version i size w FileStorage
                    existing_file.current_version = new_version_number
                    existing_file.size = file_size
                    existing_file.updated_at = datetime.now(timezone.utc)
                    self.db.add(existing_file)

                    await self.db.commit()
                    await self.db.refresh(new_version)
                except Exception as e:
                    await self.db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Database error: {str(e)}",
                    )

                # Zaktualizuj użyte miejsce (dodaj różnicę)
                size_diff = file_size / (1024 * 1024)
                user.used_storage_mb += size_diff
                try:
                    self.db.add(user)
                    await self.db.commit()
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
                    file_id=existing_file.id,
                    details={
                        "version": new_version_number,
                        "size": file_size,
                        "path": new_version.path,
                        "ip_address": ip_address
                    }
                )

                return {
                    "message": "New version uploaded successfully",
                    "file_id": str(existing_file.id),
                    "filename": base_filename,
                    "version": new_version_number,
                    "size": file_size,
                    "path": new_version.path
                }

            else:
                # Nowy plik - tworzymy pierwszą wersję
                version_number = 1
                versioned_filename = self._build_versioned_filename(base_filename, version_number)
                file_key = versioned_filename

                # Upload do S3
                try:
                    s3.upload_fileobj(BytesIO(file_content), bucket_name, file_key)
                except Exception as e:
                    raise ValueError(f"Failed to upload file: {str(e)}")

                # Utwórz nowy rekord FileStorage
                new_file = FileStorage(
                    id=uuid4(),
                    path=f"s3://{bucket_name}/{file_key}",
                    name=base_filename,
                    size=file_size,
                    owner=username,
                    current_version=version_number,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )

                # Utwórz pierwszą wersję
                first_version = FileVersion(
                    id=uuid4(),
                    file_id=new_file.id,
                    version_number=version_number,
                    path=f"s3://{bucket_name}/{file_key}",
                    size=file_size,
                    created_at=datetime.now(timezone.utc),
                    created_by=username
                )

                try:
                    self.db.add(new_file)
                    self.db.add(first_version)
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

                # Zaktualizuj użyte miejsce
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
                        "version": version_number,
                        "size": file_size,
                        "path": new_file.path,
                        "ip_address": ip_address
                    }
                )

                return {
                    "message": "File uploaded successfully",
                    "file_id": str(new_file.id),
                    "filename": base_filename,
                    "version": version_number,
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

            # Pobierz aktualną wersję na podstawie current_version
            current_version_number = file_record.current_version

            result = await self.db.execute(
                select(FileVersion).where(
                    FileVersion.file_id == file_record.id,
                    FileVersion.version_number == current_version_number
                )
            )
            current_version = result.scalar_one_or_none()

            if not current_version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {current_version_number} not found"
                )

            bucket_name = f"user-{username}"
            # Pobierz nazwę pliku z wersją z S3
            versioned_filename = self._build_versioned_filename(file_record.name, current_version_number)

            try:
                file_obj = BytesIO()
                s3.download_fileobj(bucket_name, versioned_filename, file_obj)
                file_obj.seek(0)

                await self.log_service.log_action(
                    action=LogAction.FILE_DOWNLOAD,
                    username=username,
                    status="SUCCESS",
                    file_id=file_record.id,
                    details={
                        "version": current_version_number,
                        "size": current_version.size,
                        "ip_address": ip_address
                    }
                )

                # Zwróć bazową nazwę pliku (bez _vN)
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
                    current_version_number = file_record.current_version

                    versioned_filename = self._build_versioned_filename(file_record.name, current_version_number)

                    try:
                        file_obj = BytesIO()
                        s3.download_fileobj(bucket_name, versioned_filename, file_obj)
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

            # Pobierz wszystkie wersje aby usunąć z S3
            result = await self.db.execute(
                select(FileVersion).where(FileVersion.file_id == file_record.id)
            )
            versions = result.scalars().all()

            bucket_name = f"user-{username}"
            total_size = 0

            # Usuń wszystkie wersje z S3
            for version in versions:
                versioned_filename = self._build_versioned_filename(file_record.name, version.version_number)
                try:
                    s3.delete_object(Bucket=bucket_name, Key=versioned_filename)
                    total_size += version.size
                except Exception as e:
                    # Kontynuuj nawet jeśli usuwanie jednego pliku się nie powiedzie
                    print(f"Warning: Failed to delete version {version.version_number} from S3: {str(e)}")

            # Zaktualizuj użyte miejsce
            try:
                user.used_storage_mb -= total_size / (1024 * 1024)
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

            # Usuń rekord z bazy (cascade usunie również wersje)
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
                    "size": total_size,
                    "versions_count": len(versions),
                    "ip_address": ip_address
                }
            )

            return {"message": f"File '{file_record.name}' deleted successfully with {len(versions)} version(s)"}
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

    async def get_file_versions(self, file_id: str, username: str) -> List[dict]:
        """
        Zwraca listę wszystkich wersji pliku
        """
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

            # Pobierz wszystkie wersje
            result = await self.db.execute(
                select(FileVersion).where(
                    FileVersion.file_id == file_record.id
                ).order_by(FileVersion.version_number.desc())
            )
            versions = result.scalars().all()

            return [
                {
                    "version_number": v.version_number,
                    "size": v.size,
                    "created_at": v.created_at.isoformat(),
                    "created_by": v.created_by,
                    "is_current": v.version_number == file_record.current_version
                }
                for v in versions
            ]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch versions: {str(e)}"
            )

    async def download_file_version(self, file_id: str, version_number: int, username: str, ip_address: str = None):
        """
        Pobiera konkretną wersję pliku
        """
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

            # Pobierz konkretną wersję
            result = await self.db.execute(
                select(FileVersion).where(
                    FileVersion.file_id == file_record.id,
                    FileVersion.version_number == version_number
                )
            )
            version = result.scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {version_number} not found"
                )

            bucket_name = f"user-{username}"
            versioned_filename = self._build_versioned_filename(file_record.name, version_number)

            try:
                file_obj = BytesIO()
                s3.download_fileobj(bucket_name, versioned_filename, file_obj)
                file_obj.seek(0)

                await self.log_service.log_action(
                    action=LogAction.FILE_DOWNLOAD,
                    username=username,
                    status="SUCCESS",
                    file_id=file_record.id,
                    details={
                        "version": version_number,
                        "size": version.size,
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
                    "version": version_number,
                    "ip_address": ip_address
                }
            )
            raise

    async def restore_file_version(self, file_id: str, version_number: int, username: str, ip_address: str = None) -> dict:
        """
        Przywraca konkretną wersję pliku (zmienia tylko current_version w bazie)
        """
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

            # Sprawdź czy wersja istnieje
            result = await self.db.execute(
                select(FileVersion).where(
                    FileVersion.file_id == file_record.id,
                    FileVersion.version_number == version_number
                )
            )
            version = result.scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {version_number} not found"
                )

            old_version = file_record.current_version

            # Zmień tylko current_version w bazie
            file_record.current_version = version_number
            file_record.size = version.size
            file_record.updated_at = datetime.now(timezone.utc)

            try:
                self.db.add(file_record)
                await self.db.commit()
                await self.db.refresh(file_record)
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to restore version: {str(e)}"
                )

            await self.log_service.log_action(
                action="FILE_RESTORE_VERSION",
                username=username,
                status="SUCCESS",
                file_id=file_record.id,
                details={
                    "from_version": old_version,
                    "to_version": version_number,
                    "ip_address": ip_address
                }
            )

            return {
                "message": f"File restored to version {version_number}",
                "file_id": str(file_record.id),
                "current_version": file_record.current_version,
                "filename": file_record.name
            }
        except Exception as e:
            await self.log_service.log_action(
                action="FILE_RESTORE_VERSION",
                username=username,
                status="FAILED",
                file_id=file_id,
                details={
                    "error": str(e),
                    "version": version_number,
                    "ip_address": ip_address
                }
            )
            raise

    async def delete_file_version(self, file_id: str, version_number: int, username: str, ip_address: str = None) -> dict:
        """
        Usuwa konkretną wersję pliku (nie można usunąć current_version)
        """
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

            # Nie można usunąć aktualnej wersji
            if version_number == file_record.current_version:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete current version. Restore another version first."
                )

            # Sprawdź czy wersja istnieje
            result = await self.db.execute(
                select(FileVersion).where(
                    FileVersion.file_id == file_record.id,
                    FileVersion.version_number == version_number
                )
            )
            version = result.scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {version_number} not found"
                )

            bucket_name = f"user-{username}"
            versioned_filename = self._build_versioned_filename(file_record.name, version_number)

            # Usuń z S3
            try:
                s3.delete_object(Bucket=bucket_name, Key=versioned_filename)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete file from S3: {str(e)}"
                )

            # Zaktualizuj użyte miejsce
            result = await self.db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

            user.used_storage_mb -= version.size / (1024 * 1024)
            if user.used_storage_mb < 0:
                user.used_storage_mb = 0

            try:
                self.db.add(user)
                await self.db.delete(version)
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete version from database: {str(e)}"
                )

            await self.log_service.log_action(
                action="FILE_DELETE_VERSION",
                username=username,
                status="SUCCESS",
                file_id=file_record.id,
                details={
                    "version": version_number,
                    "size": version.size,
                    "ip_address": ip_address
                }
            )

            return {
                "message": f"Version {version_number} deleted successfully",
                "file_id": str(file_record.id),
                "filename": file_record.name
            }
        except Exception as e:
            await self.log_service.log_action(
                action="FILE_DELETE_VERSION",
                username=username,
                status="FAILED",
                file_id=file_id,
                details={
                    "error": str(e),
                    "version": version_number,
                    "ip_address": ip_address
                }
            )
            raise
