from datetime import datetime
from io import BytesIO

from db.database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, HTTPException, Depends, \
    status, Request
from models.models import User
from schemas.file import FileSetIsFavorite, FileDownloadManyFiles
from services.log_service import LogService
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/download/{limit}", status_code=status.HTTP_200_OK)
async def download_logs(
        limit: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for downloading log files

    - **limit**: Number of most recent log entries to include
    """

    if not user.user_type == 'admin':
        raise HTTPException(status_code=403,
                            detail="Not authorized to access logs.")

    try:
        ip_address = request.client.host if request.client else None
        log_content = await LogService(db).get_logs(
            limit=limit,
            username=user.username,
            ip_address=ip_address
        )

        file_bytes = BytesIO(log_content.encode('utf-8'))

        filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        return StreamingResponse(
            file_bytes,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Error downloading logs: {str(e)}")
