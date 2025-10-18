from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.database import get_db
from models.models import User
from core.security import decode_access_token, now_utc

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    decoded = decode_access_token(token)
    if not decoded:
        raise credentials_exception

    username, exp = decoded

    if exp < str(now_utc().timestamp()):
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception

    return user
