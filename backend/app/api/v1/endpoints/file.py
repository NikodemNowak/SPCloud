from db.database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, Request
from fastapi.responses import StreamingResponse
from models.models import User
from schemas.file import FileSetIsFavorite, FileDownloadManyFiles, StorageInfo
from services.file_service import FileService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
        request: Request,
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to upload a file
    - **file**: File to upload
    """
    try:
        ip_address = request.client.host if request.client else None
        return await FileService(db).upload_file(file=file, username=user.username, ip_address=ip_address)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/", status_code=status.HTTP_200_OK)
async def list_files(db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    Endpoint to list files
    """
    files = await FileService(db).list_files(username=user.username)
    return {"files": files}


@router.get("/me", status_code=status.HTTP_200_OK, response_model=StorageInfo)
async def get_my_storage_info(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint returning storage information about the current user

    Returns:
    - **username**: Username
    - **total_files**: Number of files
    - **total_size_bytes**: Total size of files in bytes
    - **total_size_mb**: Total size of files in MB
    - **max_storage_mb**: Maximum storage limit in MB
    - **used_storage_mb**: Used storage in MB
    - **available_storage_mb**: Available storage in MB
    - **storage_usage_percentage**: Storage usage percentage
    - **total_favorite_files**: Number of favorite files
    - **total_versions**: Total number of file versions
    - **total_versions_size_bytes**: Total size of all versions in bytes
    - **total_versions_size_mb**: Total size of all versions in MB
    """
    try:
        return await FileService(db).get_user_storage_info(username=user.username)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching storage info: {str(e)}")


@router.get("/download/{file_id}", status_code=status.HTTP_200_OK)
async def download_file(
        file_id: str,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to download a file by ID

    - **file_id**: UUID of the file to download
    """
    ip_address = request.client.host if request.client else None
    file_obj, filename, file_size = await FileService(db).download_file(file_id=file_id, username=user.username,
                                                             ip_address=ip_address)

    try:
        return StreamingResponse(
            file_obj,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                "Content-Length": str(file_size)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@router.post("/download", status_code=status.HTTP_200_OK)
async def download_many_files(
        files: FileDownloadManyFiles,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to download multiple files as a ZIP archive
    - **files**: Object containing a list of file IDs to download
    """
    ip_address = request.client.host if request.client else None
    zip_obj, zip_filename, zip_size = await FileService(db).get_many_files(file_ids=files.file_ids, username=user.username,
                                                                 ip_address=ip_address)

    try:
        return StreamingResponse(
            zip_obj,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{zip_filename}",
                "Content-Length": str(zip_size)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading files: {str(e)}")


@router.delete("/{file_id}", status_code=status.HTTP_200_OK)
async def delete_file(
        file_id: str,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to delete a file by ID

    - **file_id**: UUID of the file to delete
    """
    try:
        ip_address = request.client.host if request.client else None
        return await FileService(db).delete_file(file_id=file_id, username=user.username, ip_address=ip_address)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.post("/change-is-favorite", status_code=status.HTTP_200_OK)
async def set_favorite_file(file: FileSetIsFavorite,
                            request: Request,
                            user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    """
    Endpoint to set or unset a file as favorite

    - **file_favorite**: Object containing file ID and favorite status
    """
    try:
        ip_address = request.client.host if request.client else None
        return await FileService(db).set_favorite_file(file_id=file.file_id, is_favorite=file.is_favorite,
                                                       username=user.username, ip_address=ip_address)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/{file_id}/versions", status_code=status.HTTP_200_OK)
async def get_file_versions(
        file_id: str,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to get all versions of a file

    - **file_id**: UUID of the file
    """
    try:
        versions = await FileService(db).get_file_versions(file_id=file_id, username=user.username)
        return {"file_id": file_id, "versions": versions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching versions: {str(e)}")


@router.get("/{file_id}/versions/{version_number}", status_code=status.HTTP_200_OK)
async def download_file_version(
        file_id: str,
        version_number: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to download a specific version of a file

    - **file_id**: UUID of the file
    - **version_number**: Version number to download
    """
    try:
        ip_address = request.client.host if request.client else None
        file_obj, filename = await FileService(db).download_file_version(
            file_id=file_id,
            version_number=version_number,
            username=user.username,
            ip_address=ip_address
        )

        return StreamingResponse(
            file_obj,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading version: {str(e)}")


@router.post("/{file_id}/restore/{version_number}", status_code=status.HTTP_200_OK)
async def restore_file_version(
        file_id: str,
        version_number: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to restore a specific version of a file (changes current_version in database)

    - **file_id**: UUID of the file
    - **version_number**: Version number to restore
    """
    try:
        ip_address = request.client.host if request.client else None
        return await FileService(db).restore_file_version(
            file_id=file_id,
            version_number=version_number,
            username=user.username,
            ip_address=ip_address
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring version: {str(e)}")


@router.delete("/{file_id}/versions/{version_number}", status_code=status.HTTP_200_OK)
async def delete_file_version(
        file_id: str,
        version_number: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to delete a specific version of a file (cannot delete current version)

    - **file_id**: UUID of the file
    - **version_number**: Version number to delete
    """
    try:
        ip_address = request.client.host if request.client else None
        return await FileService(db).delete_file_version(
            file_id=file_id,
            version_number=version_number,
            username=user.username,
            ip_address=ip_address
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting version: {str(e)}")

