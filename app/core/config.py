from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API Settings
    PROJECT_NAME: str = "Kvitta API"
    API_V1_STR: str = "/api/v1"
    PROJECT_VERSION: str = "0.1.0"
    DESCRIPTION: str = "Receipt splitting and expense management API"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "kvitta"

    # API Keys
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    NVIDIA_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # JWT
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # File Upload
    MAX_FILE_SIZE: int = 10485760
    UPLOAD_DIR: str = "uploads"

    # Azure Storage
    STORAGE_CONNECTION_STRING: str = ""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env"
    )

settings = Settings()
