from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, UniqueConstraint
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

    __table_args__ = (
        UniqueConstraint('owner', 'name', name='uq_owner_filename'),
    )


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
    user_type = Column(String, default="regular")  # 'admin', 'regular'
    max_storage_mb = Column(Integer, default=100)  # Default 100 MB
    used_storage_mb = Column(Integer, default=0)  # Used storage in MB
    totp_secret = Column(String, nullable=True)
    totp_configured = Column(Boolean, default=False)

    files = relationship("FileStorage", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("LogEntry", back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_username = Column(String, ForeignKey("users.username", ondelete="CASCADE"), nullable=False)
    token = Column(String, nullable=False, index=True, unique=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True))

    user = relationship("User", back_populates="refresh_tokens")


class LogEntry(Base):
    __tablename__ = "logs"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    action = Column(String)
    status = Column(String)
    username = Column(String, ForeignKey("users.username", ondelete="CASCADE"), nullable=False)
    file_id = Column(UUID(as_uuid=True), nullable=True)
    timestamp = Column(TIMESTAMP(timezone=True))
    details = Column(String, nullable=True)

    user = relationship("User", back_populates="logs")
