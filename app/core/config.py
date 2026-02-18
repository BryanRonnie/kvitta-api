from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Kvitta API"
    API_V1_STR: str = "/api/v1"
    
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "kvitta"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env"
    )

settings = Settings()
