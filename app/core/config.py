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
    SQL_ECHO: bool = False  # Set to True to log all SQL queries (very verbose)
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx"]
    
    # RAG Configuration
    # LLM Settings (dynamic - can be changed via config)
    LLM_PROVIDER: str = "gemini"  # gemini, groq, openai, anthropic, etc.
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = "gemini-2.5-flash-lite"  # Model name (e.g., "gemini-pro", "gpt-4", etc.)
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    
    # Groq Settings (for text enhancement)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL_NAME: str = "llama-3.3-70b-versatile"  # Groq model name
    TEXT_ENHANCEMENT_ENABLED: bool = True  # Enable LLM text enhancement before chunking
    TEXT_ENHANCEMENT_TEMPERATURE: float = 0.3  # Low temperature to prevent hallucination
    
    # Embedding Settings (dynamic - can be changed via config)
    EMBEDDING_PROVIDER: str = "sentence-transformers"  # sentence-transformers, openai, etc.
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"  # Default sentence-transformers model
    EMBEDDING_API_KEY: Optional[str] = None  # For API-based embeddings
    
    # Vector Store Settings
    VECTOR_STORE_TYPE: str = "faiss"  # faiss, pinecone, weaviate, etc.
    VECTOR_STORE_PATH: str = "./data/vector_store"  # Local path for FAISS
    VECTOR_DIMENSION: int = 384  # Dimension for all-MiniLM-L6-v2, adjust based on model
    
    # RAG Settings
    RAG_CHUNK_SIZE: int = 1000  # Characters per chunk
    RAG_CHUNK_OVERLAP: int = 200  # Overlap between chunks
    RAG_TOP_K: int = 10  # Number of relevant chunks to retrieve
    RAG_SIMILARITY_THRESHOLD: float = 0.1  # Minimum similarity score for retrieval
    
    # Document Processing
    DOCUMENTS_STORAGE_PATH: str = "./data/documents"  # Local filesystem path
    OCR_ENABLED: bool = True
    OCR_LANGUAGE: str = "eng"  # Tesseract language code
    USE_DEEPDOCTECTION: bool = False  # Use DeepDocDetection for layout-aware PDF/image parsing
    
    # Conversation/Memory Settings
    CONVERSATION_HISTORY_LIMIT: int = 10  # Number of previous messages to include in context
    SESSION_TIMEOUT_HOURS: int = 24  # Session timeout in hours
    
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

