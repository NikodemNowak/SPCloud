from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.v1.api import api_router
from init_db import init_db
from fastapi.middleware.cors import CORSMiddleware

# Special object to manage the lifespan of the app
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing application...")
    # Initialize the database
    await init_db()
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

# Configure CORS so the frontend dev server(s) can access the API
origins = [
    "http://localhost:5173",   # default Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",   # in case another dev server is used
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Hello World"}


# We include in our main `app` application all the endpoints defined
# in the `api_router` object that we imported at the beginning.
# This way, all the routes defined in `api_router` will be available under the `/api/v1` prefix.
app.include_router(api_router, prefix="/api/v1")
