from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.security import decode_access_token, now_utc, _jwt_keys_and_alg
from db.database import get_db
from models.models import User

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


async def get_user_for_totp_setup(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid setup token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    expired_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Setup token expired. Please request a new one.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        signing_key, alg = _jwt_keys_and_alg()
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            options={
                "require_sub": True,
                "require_exp": True,
            }
        )
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        exp: int = payload.get("exp")

        if username is None or token_type != "totp_setup":
            raise credentials_exception

        if exp < now_utc().timestamp():
            raise expired_exception

    except JWTError as e:
        error_msg = str(e).lower()
        if "expired" in error_msg or "signature has expired" in error_msg:
            raise expired_exception
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if user.totp_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP already configured"
        )

    return user
