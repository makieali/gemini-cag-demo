"""Application configuration, loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str) -> bool:
    return str(value).lower() in ("true", "1", "t", "yes")


class Config:
    """Flask + Gemini configuration sourced from the environment."""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = _as_bool(os.getenv("FLASK_DEBUG", "false"))
    PORT = int(os.getenv("PORT", "5069"))

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

    # Uploads
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "temp_uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "32")) * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        "pdf", "txt", "md", "doc", "docx",
        "csv", "xlsx", "ppt", "pptx", "json",
    }

    @classmethod
    def require_api_key(cls) -> str:
        """Return the API key or raise if it is missing/placeholder."""
        key = cls.GEMINI_API_KEY
        if not key or key in ("YOUR_GEMINI_API_KEY", "your-gemini-api-key-here"):
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. Copy .env.example to .env "
                "and set a real key from https://aistudio.google.com/apikey"
            )
        return key
