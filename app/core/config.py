import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application configuration."""
    
    # MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI")
    MONGODB_DB = os.getenv("DATABASE_NAME", "kvitta")
    
    # JWT
    JWT_SECRET = os.getenv("SECRET_KEY", "kvitta-super-secret-jwt-key-change-this-in-production")
    JWT_ALGORITHM = os.getenv("ALGORITHM", "HS256")
    JWT_EXPIRATION_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # App
    APP_NAME = os.getenv("PROJECT_NAME", "Kvitta API")
    APP_VERSION = os.getenv("PROJECT_VERSION", "0.1.0")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

settings = Settings()
