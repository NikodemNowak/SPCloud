from core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_refresh_token, now_utc
from fastapi import HTTPException, status
from models.models import User, RefreshToken
from schemas.user import UserCreate, UserLogin, Token, RefreshTokenRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging
import uuid


logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _create_tokens(self, username: str) -> Token:
        access_token = create_access_token(username)
        refresh_token_str, expires_at = create_refresh_token(username)

        refresh_token_obj = RefreshToken(
            id=uuid.uuid4(),
            user_username=username,
            token=refresh_token_str,
            expires_at=expires_at,
            created_at=now_utc()
        )

        self.db.add(refresh_token_obj)
        await self.db.commit()

        return Token(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer"
        )

    async def register(self, user_data: UserCreate):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

        new_user = User(
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            user_type="regular"
        )

        try:
            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )

        return await self._create_tokens(new_user.username)

    async def login(self, user_data: UserLogin):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        user = result.scalar_one_or_none()

        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info("User logged in: %s", user.username)
        return await self._create_tokens(user.username)

    async def refresh_access_token(self, refresh_token_request: RefreshTokenRequest) -> Token:
        refresh_token_str = refresh_token_request.refresh_token

        username = decode_refresh_token(refresh_token_str)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        )
        token_obj = result.scalar_one_or_none()

        if not token_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if token_obj.expires_at < now_utc():
            await self.db.delete(token_obj)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(username)

        logger.info("Access token refreshed for user: %s", username)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer"
        )

    async def logout(self, refresh_token_request: RefreshTokenRequest) -> dict:
        refresh_token_str = refresh_token_request.refresh_token

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        )
        token_obj = result.scalar_one_or_none()

        if token_obj:
            await self.db.delete(token_obj)
            await self.db.commit()
            logger.info("User logged out: %s", token_obj.user_username)

        return {"message": "Logged out successfully"}

    async def cleanup_expired_tokens(self) -> int:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.expires_at < now_utc())
        )
        expired_tokens = result.scalars().all()

        count = len(expired_tokens)
        for token in expired_tokens:
            await self.db.delete(token)

        await self.db.commit()
        logger.info("Cleaned up %d expired refresh tokens", count)
        return count
