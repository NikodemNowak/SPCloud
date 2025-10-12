from fastapi import APIRouter
from .endpoints import file

api_router = APIRouter()

# Including the file router
api_router.include_router(file.router)

