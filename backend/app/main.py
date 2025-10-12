from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.v1.api import api_router
from init_db import init_db

# Sepecial object to manage the lifespan of the app
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing application...")
    # Initialize the database
    init_db()
    # yield is used to separate startup and shutdown code
    yield
    print("Shutting down application...")

# Creating the FastAPI app
app = FastAPI(
    title="SPCloud API",
    description="API to manage files in SPCloud",
    version="1.0.0",
    # We tell the FastAPI instance to use our `lifespan` function to manage its lifecycle.
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Hello World"}


# We include in our main `app` application all the endpoints defined
# in the `api_router` object that we imported at the beginning.
# This way, all the routes defined in `api_router` will be available under the `/api/v1` prefix.
app.include_router(api_router, prefix="/api/v1")
