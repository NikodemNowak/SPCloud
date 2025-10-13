from typing import Optional

from db.database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi import Depends, status
from models.models import User
from services.file_service import FileService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        logical_name: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for uploading files

    - **file**: File to upload
    - **logical_name**: Optional logical name of the file
    """
    try:
        return await FileService(db).save_file(file=file, username=user.username, logical_name=logical_name)
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
