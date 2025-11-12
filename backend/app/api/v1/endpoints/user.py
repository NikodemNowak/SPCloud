from db.database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, Depends, status, HTTPException, Request
from models.models import User
from schemas.totp import TOTPSetupToken
from schemas.user import UserCreate, Token, UserLogin, RefreshTokenRequest, UserLoginWithTOTP
from services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=TOTPSetupToken, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)) -> TOTPSetupToken:
    try:
        ip_address = request.client.host if request.client else None
        return await UserService(db).register(user_data, ip_address)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during registration: {str(e)}")


@router.post("/login", response_model=Union[Token, TOTPSetupToken], status_code=status.HTTP_200_OK)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)) -> Union[Token, TOTPSetupToken]:
    try:
        return await UserService(db).login(user_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")


@router.post("/login/totp", response_model=Token, status_code=status.HTTP_200_OK)
async def login_with_totp(
        user_data: UserLoginWithTOTP,
        db: AsyncSession = Depends(get_db)
) -> Token:
    try:
        return await UserService(db).login_with_totp(user_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")


@router.post("/refresh", response_model=Token, status_code=status.HTTP_200_OK)
async def refresh_token(
        refresh_data: RefreshTokenRequest,
        db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Odświeża access token używając refresh tokenu
    """
    return await UserService(db).refresh_access_token(refresh_data)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Wylogowuje użytkownika - usuwa wszystkie jego refresh tokeny
    """
    try:
        ip_address = request.client.host if request.client else None
        return await UserService(db).logout(current_user.username, ip_address)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during logout: {str(e)}")


@router.get("/isadmin", status_code=status.HTTP_200_OK)
async def is_admin(
        current_user: User = Depends(get_current_user)
):
    """
    Sprawdza czy aktualny użytkownik jest administratorem
    """
    try:
        return current_user.user_type == "admin"
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking admin status: {str(e)}")
