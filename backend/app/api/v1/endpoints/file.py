from db.database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, Request
from fastapi.responses import StreamingResponse
from models.models import User
from schemas.file import FileSetIsFavorite, FileDownloadManyFiles
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
    Endpoint for uploading files

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
    Endpoint returning a list of all files
    """
    files = await FileService(db).list_files(username=user.username)
    return {"files": files}


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
    file_obj, filename = await FileService(db).download_file(file_id=file_id, username=user.username,
                                                             ip_address=ip_address)

    try:
        return StreamingResponse(
            file_obj,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/download", status_code=status.HTTP_200_OK)
async def download_many_files(
        files: FileDownloadManyFiles,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to download multiple files as a ZIP archive
    - **files**: Object containing list of file IDs to download
    """
    ip_address = request.client.host if request.client else None
    zip_obj, zip_filename = await FileService(db).get_many_files(file_ids=files.file_ids, username=user.username,
                                                                 ip_address=ip_address)

    try:
        return StreamingResponse(
            zip_obj,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{zip_filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


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
