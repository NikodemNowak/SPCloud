"""
Script to initialize the database by creating tables if they do not exist.
"""
import os
from sqlalchemy import create_engine
from models.models import Base

def init_db():

    # Download DATABASE_URL from environment variable or use a default value
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:secret@db:5432/mydb")
    print(f"Connecting to db: {DATABASE_URL}")

    # Creates a database engine.
    # This is the object that manages database connections. It is configured via a URL.
    engine = create_engine(DATABASE_URL)

    print("Adding all tables to the database...")
    # `Base.metadata` is an object containing the schema of all tables defined in models (everything that inherits from `Base`).
    # `.create_all(engine)` is a method that says: "Iterate through all tables
    # in this schema and for each one send a CREATE TABLE command to the database (via `engine`), but only IF that table does not already exist."
    Base.metadata.create_all(engine)
    print("tables created successfully.")

if __name__ == "__main__":
    init_db()

