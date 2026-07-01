from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./yeshiva_alumni.db"

    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    APP_NAME: str = "מערכת ניהול בוגרי ישיבה"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    API_HOST: str = "localhost"
    API_PORT: int = 8000

    @property
    def effective_secret_key(self) -> str:
        if self.SECRET_KEY:
            return self.SECRET_KEY
        if self.DEBUG:
            return "dev-only-insecure-key-do-not-use-in-production"
        raise RuntimeError("SECRET_KEY לא הוגדר ב-.env")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
