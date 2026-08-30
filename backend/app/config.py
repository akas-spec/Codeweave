from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App
    APP_NAME: str = "CodeWeave"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://codeweave:codeweave@localhost:5434/codeweave"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    
    # GitHub OAuth
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    
    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # Ingestion
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    REPOS_DIR: str = "./repos"
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
