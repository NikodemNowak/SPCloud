"""
Script to initialize the database by creating tables if they do not exist.
"""
import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings
from models.models import Base


async def init_db():
    # Creates a database engine.
    # This is the object that manages database connections. It is configured via a URL.
    engine = create_async_engine(settings.DB_URL, echo=True)

    print("Adding all tables to the database...")
    # `Base.metadata` is an object containing the schema of all tables defined in models (everything that inherits from `Base`).
    # `.create_all(engine)` is a method that says: "Iterate through all tables
    # in this schema and for each one send a CREATE TABLE command to the database (via `engine`), but only IF that table does not already exist."
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
