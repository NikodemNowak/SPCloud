from typing import Union

from db.database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, Depends, status, HTTPException, Request
from schemas.totp import TOTPSetupToken
from schemas.user import UserCreate, Token, UserLogin, UserLoginWithTOTP
from services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: str = Depends(get_current_user)
):
    try:
        ip_address = request.client.host if request.client else None
        await UserService(db).logout(current_user, ip_address)
        return {"message": "Logged out successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during logout: {str(e)}")
