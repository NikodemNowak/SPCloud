from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_URL: str = "postgresql+asyncpg://user:secret@db:5432/mydb"
    JWT_SECRET: str = "supersecret"
    JWT_EXPIRE_MIN: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "SPCloud"

    class Config:
        env_file = ".env"

settings = Settings()
