from core.security import hash_password, verify_password, create_access_token
from fastapi import HTTPException, status
from models.models import User
from schemas.user import UserCreate, UserLogin, Token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

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

        token = create_access_token(new_user.username)
        return Token(access_token=token, token_type="bearer")

    async def login(self, user_data: UserLogin):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        user = result.scalar_one_or_none()

        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(user.username)
        logger.info("User logged in: %s", user.username)
        return Token(access_token=token, token_type="bearer")
