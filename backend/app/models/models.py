from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, LargeBinary
Base = declarative_base()

class FileStorage(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    logical_name = Column(String, unique=True)
    content_type = Column(String)
    size = Column(Integer)
    data = Column(LargeBinary)
    owner = Column(String, foregin_key="users.username")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

