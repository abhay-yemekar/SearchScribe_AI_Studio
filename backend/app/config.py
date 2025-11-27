# backend/app/config.py
import os
from functools import lru_cache

from dotenv import load_dotenv  # 👈 NEW

# Load variables from .env file into environment
load_dotenv()  # 👈 NEW


class Settings:
    """
    Central config object for the backend.
    """

    # JWT / auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-.env")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Database
    SQLALCHEMY_DATABASE_URL: str = os.getenv(
        "SQLALCHEMY_DATABASE_URL", "sqlite:///./searchscribe.db"
    )

    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME: str = os.getenv(
        "GEMINI_MODEL_NAME", "gemini-2.5-flash"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
