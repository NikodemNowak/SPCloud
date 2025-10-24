import uuid
from io import BytesIO

import pyotp
import qrcode
from core.security import create_access_token, create_refresh_token
from core.security import now_utc
from fastapi import HTTPException, status
from models.models import User, RefreshToken
from schemas.user import Token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


class TOTPService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_totp_secret(self, username: str) -> dict:
        """Generate TOTP secret and QR code for user"""
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.totp_configured:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP already configured"
            )

        # Generate secret
        secret = pyotp.random_base32()
        user.totp_secret = secret

        try:
            await self.db.commit()
            await self.db.refresh(user)
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save TOTP secret: {str(e)}"
            )

        # Generate provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=username,
            issuer_name="SPCloud"
        )

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        return {
            "secret": secret,
            "qr_code": img_buffer,
            "provisioning_uri": provisioning_uri
        }

    async def verify_totp(self, username: str, code: str) -> bool:
        """Verify TOTP code and mark as configured"""
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user or not user.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP not initialized"
            )

        totp = pyotp.TOTP(user.totp_secret)

        if not totp.verify(code, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code"
            )

        if not user.totp_configured:
            user.totp_configured = True
            try:
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update TOTP status: {str(e)}"
                )

        return True

    async def verify_and_issue_token(self, username: str, code: str) -> Token:
        """Verify TOTP code, mark as configured and issue access token"""
        await self.verify_totp(username, code)

        return await create_token_pair(self.db, username)

    async def check_totp_required(self, username: str) -> bool:
        """Check if user needs to configure TOTP"""
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            return False

        return not user.totp_configured


async def create_token_pair(db: AsyncSession, username: str) -> Token:
    access_token = create_access_token(username)
    refresh_token_str, expires_at = create_refresh_token(username)

    refresh_token_obj = RefreshToken(
        id=uuid.uuid4(),
        user_username=username,
        token=refresh_token_str,
        expires_at=expires_at,
        created_at=now_utc()
    )

    db.add(refresh_token_obj)
    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer"
    )
