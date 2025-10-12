from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.v1.api import api_router
from init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing application...")
    init_db()
    yield # yield is used to separate startup and shutdown code
    print("Shutting down application...")


app = FastAPI(
    title="SPCloud API",
    description="API to manage files in SPCloud",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Hello World"}


# Turning on the API router
app.include_router(api_router, prefix="/api/v1")
