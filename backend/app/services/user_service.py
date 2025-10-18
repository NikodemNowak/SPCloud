from core.security import hash_password, verify_password, create_access_token, create_totp_setup_token
from fastapi import HTTPException, status
from models.models import User
from schemas.user import UserCreate, UserLogin, Token, UserLoginWithTOTP
from schemas.totp import TOTPSetupToken
from services.totp_service import TOTPService
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


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
            user_type="regular",
            totp_secret=None,
            totp_configured=False
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

        setup_token = create_totp_setup_token(new_user.username)

        return TOTPSetupToken(
            setup_token=setup_token,
            token_type="bearer",
            expires_in=900  # 15 minutes
        )

    async def login(self, user_data: UserLogin):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        user = result.scalar_one_or_none()

        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.totp_configured:
            setup_token = create_totp_setup_token(user.username)
            return TOTPSetupToken(
                setup_token=setup_token,
                token_type="bearer",
                expires_in=900
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TOTP verification required. Use /users/login/totp"
        )

    async def login_with_totp(self, user_data: UserLoginWithTOTP):
        result = await self.db.execute(select(User).where(User.username == user_data.username))
        user = result.scalar_one_or_none()

        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.totp_configured:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TOTP not configured"
            )

        await TOTPService(self.db).verify_totp(user.username, user_data.totp_code)

        token = create_access_token(user.username)
        return Token(access_token=token, token_type="bearer")
