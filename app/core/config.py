"""
Application configuration management
"""
import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Onboarding API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    WORKERS: Optional[int] = None  # Auto-calculated if None
    RELOAD: bool = False  # Set to True for development
    START_CELERY: bool = True  # Start Celery worker with server
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "Onboarding API"
    API_DESCRIPTION: str = "Onboarding API with FastAPI, Celery, and Webhooks"
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]
    
    # Database (if needed)
    DATABASE_URL: Optional[str] = None
    
    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    REDIS_CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # Webhooks
    WEBHOOK_SECRET: Optional[str] = None
    WEBHOOK_TIMEOUT: int = 30  # seconds
    WEBHOOK_MAX_RETRIES: int = 3
    
    # Twilio WhatsApp
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_NUMBER: Optional[str] = None  # Format: whatsapp:+14155238886
    TWILIO_WEBHOOK_URL: Optional[str] = None  # Your public webhook URL
    TWILIO_VERIFY_TOKEN: Optional[str] = None  # For webhook verification
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx"]
    
    @field_validator("WORKERS", mode="before")
    @classmethod
    def parse_workers(cls, v):
        """Parse WORKERS, handling empty strings"""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

