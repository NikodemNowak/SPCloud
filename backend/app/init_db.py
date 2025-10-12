"""
Script to initialize the database by creating tables if they do not exist.
"""
import os
from sqlalchemy import create_engine
from models.models import Base

def init_db():

    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:secret@db:5432/mydb")
    print(f"Connecting to db: {DATABASE_URL}")

    # Object to communicate with the database
    engine = create_engine(DATABASE_URL)

    print("Adding all tables to the database...")
    Base.metadata.create_all(engine)
    print("tables created successfully.")

if __name__ == "__main__":
    init_db()

