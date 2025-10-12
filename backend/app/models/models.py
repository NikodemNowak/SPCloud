from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class FileStorage(Base):
    __tablename__ = "files"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    path = Column(String)
    name = Column(String)
    size = Column(Integer)
    owner = Column(String, ForeignKey("users.username"))
    current_version = Column(Integer, default=1)
    created_at = Column(TIMESTAMP(timezone=True))
    updated_at = Column(TIMESTAMP(timezone=True))
    is_favorite = Column(Boolean, default=False)

    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan")
    user = relationship("User", back_populates="files")


class FileVersion(Base):
    __tablename__ = "file_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"))
    version_number = Column(Integer)
    path = Column(String)
    size = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True))
    created_by = Column(String, ForeignKey("users.username"))

    file = relationship("FileStorage", back_populates="versions")
    creator = relationship("User", foreign_keys=created_by)


class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    hashed_password = Column(String)
    user_type = Column(String)  # 'admin', 'regular'

    files = relationship("FileStorage", back_populates="user")


class LogEntry(Base):
    __tablename__ = "logs"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    action = Column(String)
    username = Column(String, ForeignKey("users.username"))
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    timestamp = Column(TIMESTAMP(timezone=True))
    details = Column(String, nullable=True)
