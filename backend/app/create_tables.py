import os
from sqlalchemy import create_engine
from models.models import Base

# Download DATABASE_URL from environment variable or use a default value
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:secret@db:5432/mydb")
engine = create_engine(DATABASE_URL)

# Create all tables in the database
Base.metadata.create_all(engine)

print("Tables created successfully.")

# To run this script in docker container, use:
# docker-compose run backend python app/create_tables.py

