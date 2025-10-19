import json
from datetime import datetime, timezone
from uuid import uuid4

from models.models import LogEntry
from sqlalchemy.ext.asyncio import AsyncSession


class LogAction:
    # User actions
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"

    # File actions
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    FILE_MANY_DOWNLOAD = "FILE_MANY_DOWNLOAD"
    FILE_DELETE = "FILE_DELETE"
    FILE_UPDATE = "FILE_UPDATE"
    FILE_RENAME = "FILE_RENAME"
    FILE_FAVORITE = "FILE_FAVORITE"
    FILE_UNFAVORITE = "FILE_UNFAVORITE"

    # File version actions
    FILE_VERSION_CREATE = "FILE_VERSION_CREATE"
    FILE_VERSION_RESTORE = "FILE_VERSION_RESTORE"
    FILE_VERSION_DELETE = "FILE_VERSION_DELETE"


class LogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
            self,
            action: str,
            username: str,
            file_id: str = None,
            details: dict = None,
            status: str = "SUCCESS"
    ):
        if details is None:
            details = {}

        log_entry = LogEntry(
            id=uuid4(),
            action=action,
            username=username,
            file_id=file_id,
            timestamp=datetime.now(timezone.utc),
            details=json.dumps(details) if details else None,
            status=status,
        )

        try:
            self.db.add(log_entry)
            await self.db.commit()
            await self.db.refresh(log_entry)
        except Exception:
            await self.db.rollback()
            pass
