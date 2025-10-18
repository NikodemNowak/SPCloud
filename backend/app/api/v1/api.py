from fastapi import APIRouter

from .endpoints import file, user, totp

api_router = APIRouter()

# Including the file router
api_router.include_router(file.router)
api_router.include_router(user.router)
api_router.include_router(totp.router)
