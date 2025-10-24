import logging

from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    now_utc,
    create_totp_setup_token
)
from fastapi import HTTPException, status
from models.models import User, RefreshToken
from schemas.totp import TOTPSetupToken
from schemas.user import UserCreate, UserLogin, Token, RefreshTokenRequest, UserLoginWithTOTP
from services.log_service import LogService
from services.totp_service import TOTPService
from services.totp_service import create_token_pair
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.log_service = LogService(db)

    async def _get_and_verify_user(self, username: str, password: str) -> User:
        """
        Pobiera użytkownika i weryfikuje hasło
        """
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    async def register(self, user_data: UserCreate, ip_address: str = None) -> TOTPSetupToken:
        """
        Rejestruje nowego użytkownika i zwraca token do konfiguracji TOTP
        """
        try:
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

            await self.log_service.log_action(
                action="REGISTER",
                username=new_user.username,
                status="SUCCESS",
                details={"totp_configured": False, "ip_address": ip_address}
            )

            return TOTPSetupToken(
                setup_token=setup_token,
                token_type="bearer",
                expires_in=900  # 15 minutes
            )
        except HTTPException as e:
            await self.log_service.log_action(
                action="REGISTER",
                username=user_data.username,
                status="FAILED",
                details={"error": e.detail, "ip_address": ip_address}
            )
            raise

    async def login(self, user_data: UserLogin):
        """
        Logowanie użytkownika - zwraca setup token jeśli TOTP nie jest skonfigurowany
        """
        user = await self._get_and_verify_user(user_data.username, user_data.password)

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
        """
        Logowanie z weryfikacją TOTP - zwraca access i refresh token
        """
        try:
            user = await self._get_and_verify_user(user_data.username, user_data.password)

            if not user.totp_configured:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="TOTP not configured"
                )

            await TOTPService(self.db).verify_totp(user.username, user_data.totp_code)

            await self.log_service.log_action(
                action="LOGIN",
                username=user.username,
                status="SUCCESS",
                details={"method": "TOTP"}
            )

            return await create_token_pair(self.db, user.username)
        except HTTPException as e:
            await self.log_service.log_action(
                action="LOGIN",
                username=user_data.username,
                status="FAILED",
                details={"error": e.detail, "method": "TOTP"}
            )
            raise

    async def refresh_access_token(self, refresh_token_request: RefreshTokenRequest) -> Token:
        """
        Odświeża access token używając refresh tokenu.
        Refresh token pozostaje ten sam i jest ważny przez pełny okres od logowania.
        """
        refresh_token_str = refresh_token_request.refresh_token

        # Dekoduj refresh token
        username = decode_refresh_token(refresh_token_str)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Sprawdź czy token istnieje w bazie danych
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

        # Sprawdź czy token nie wygasł
        if token_obj.expires_at < now_utc():
            await self.db.delete(token_obj)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Sprawdź czy użytkownik istnieje
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Wygeneruj tylko nowy access token (refresh token pozostaje ten sam)
        access_token = create_access_token(username)

        logger.info("Access token refreshed for user: %s", username)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer"
        )

    async def logout(self, username: str, ip_address: str = None):
        """
        Wylogowuje użytkownika przez usunięcie wszystkich jego refresh tokenów
        """
        try:
            result = await self.db.execute(
                select(RefreshToken).where(RefreshToken.user_username == username)
            )
            tokens = result.scalars().all()

            for token in tokens:
                await self.db.delete(token)

            await self.db.commit()

            await self.log_service.log_action(
                action="LOGOUT",
                username=username,
                status="SUCCESS",
                details={"tokens_revoked": len(tokens), "ip_address": ip_address}
            )

            logger.info("User logged out: %s", username)
            return {"message": "Logged out successfully"}
        except Exception as e:
            await self.log_service.log_action(
                action="LOGOUT",
                username=username,
                status="FAILED",
                details={"error": str(e), "ip_address": ip_address}
            )
            raise

    async def cleanup_expired_tokens(self) -> int:
        """
        Usuwa wygasłe refresh tokeny z bazy danych
        Zwraca liczbę usuniętych tokenów
        """
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
