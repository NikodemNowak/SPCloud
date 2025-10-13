from typing import Optional

from dependencies import get_current_user
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi import Depends
from fastapi.responses import FileResponse
from models.models import User
from services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])
file_service = FileService()


@router.post("/upload")
async def upload_file(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        logical_name: Optional[str] = Form(None)
):
    """
    Endpoint for uploading files

    - **file**: File to upload
    - **logical_name**: Optional logical name of the file
    """
    try:
        result = await file_service.save_file(file=file, username=user.username, logical_name=logical_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/download/{file_name}")
async def download_file(file_name: str):
    """
    Endpoint for downloading files

    - **file_name**: Name of the file to download
    """
    if not file_service.file_exists(file_name):
        raise HTTPException(status_code=404, detail="File not found")

    file_path = file_service.get_file_path(file_name)
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=file_name
    )


@router.get("/")
async def list_files():
    """
    Endpoint returning a list of all files
    """
    files = file_service.list_files()
    return {"files": files}


@router.get("/{file_name}/info")
async def get_file_info(file_name: str):
    """
    Endpoint returning information about a specific file

    - **file_name**: Name of the file
    """
    info = file_service.get_file_info(file_name)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")

    return info
