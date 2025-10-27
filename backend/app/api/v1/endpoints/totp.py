import base64

from db.database import get_db
from dependencies import get_current_user, get_user_for_totp_setup
from fastapi import APIRouter, Depends, status
from models.models import User
from schemas.totp import TOTPVerifyRequest
from schemas.user import Token
from services.totp_service import TOTPService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/totp", tags=["totp"])


@router.post("/setup", status_code=status.HTTP_200_OK)
async def setup_totp(
        user: User = Depends(get_user_for_totp_setup),
        db: AsyncSession = Depends(get_db)
):
    """Generate TOTP secret and QR code"""
    result = await TOTPService(db).generate_totp_secret(user.username)

    qr_bytes = result["qr_code"].getvalue()
    qr_base64 = base64.b64encode(qr_bytes).decode('utf-8')

    return {
        "secret": result["secret"],
        "provisioning_uri": result["provisioning_uri"],
        "qr_code": f"data:image/png;base64,{qr_base64}"
    }


@router.post("/verify", response_model=Token, status_code=status.HTTP_200_OK)
async def verify_totp(
        request: TOTPVerifyRequest,
        user: User = Depends(get_user_for_totp_setup),
        db: AsyncSession = Depends(get_db)
) -> Token:
    """Verify TOTP code and complete setup"""
    return await TOTPService(db).verify_and_issue_token(user.username, request.code)


@router.get("/status", status_code=status.HTTP_200_OK)
async def totp_status(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Check if TOTP is configured"""
    needs_setup = await TOTPService(db).check_totp_required(user.username)
    return {"totp_configured": not needs_setup, "requires_setup": needs_setup}
