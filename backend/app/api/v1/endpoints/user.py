from db.database import get_db
from fastapi import APIRouter, Depends, status
from schemas.user import UserCreate, Token, UserLogin, RefreshTokenRequest
from services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/users", tags=["users"])



@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)) -> Token:
    return await UserService(db).register(user_data)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    return await UserService(db).login(user_data)


@router.post("/refresh", response_model=Token, status_code=status.HTTP_200_OK)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> Token:
    return await UserService(db).refresh_access_token(refresh_data)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await UserService(db).logout(refresh_data)
