from core.security import hash_password, verify_password, create_access_token
from models.models import User
from schemas.user import UserCreate, UserLogin, Token
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, user_data: UserCreate):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

        new_user = User(
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            user_type="regular"
        )

        try:
            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="Database error")

        token = create_access_token(new_user.username)
        print(f"[REGISTER] New user: {new_user.username}")

        return Token(access_token=token, token_type="bearer")

    async def login(self, user_data: UserLogin):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = create_access_token(user.username)
        print(f"[LOGIN] User logged in: {user.username}")

        return Token(access_token=token, token_type="bearer")
