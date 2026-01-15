"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Create database engine
engine = None
SessionLocal = None


def init_database():
    """Initialize database connection"""
    global engine, SessionLocal
    
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL not configured. Database features will be unavailable.")
        # Use in-memory SQLite as fallback (not recommended for production)
        engine = create_engine("sqlite:///:memory:", echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("✅ Database connection initialized (using in-memory SQLite fallback)")
        return
    
    try:
        # Disable SQL query logging by default (too verbose)
        # Set SQL_ECHO=true in .env if you need to debug SQL queries
        sql_echo = getattr(settings, 'SQL_ECHO', False)
        
        engine = create_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            echo=sql_echo,  # Only log SQL if explicitly enabled
        )
        
        # Suppress SQLAlchemy engine logging unless explicitly enabled
        if not sql_echo:
            logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("✅ Database connection initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {str(e)}")
        # Fallback to in-memory SQLite if connection fails
        logger.warning("Falling back to in-memory SQLite")
        try:
            engine = create_engine("sqlite:///:memory:", echo=False)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            logger.info("✅ Fallback database connection initialized")
        except Exception as fallback_error:
            logger.error(f"❌ Failed to initialize fallback database: {str(fallback_error)}")
            # Set to None so get_db() can raise proper error
            engine = None
            SessionLocal = None


def get_db() -> Session:
    """
    Get database session (dependency for FastAPI)
    Usage: db: Session = Depends(get_db)
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    if engine is None:
        logger.error("Database engine not initialized")
        return
    
    try:
        # Import all table models to register them
        from app.tables import users, knowledge_documents, user_documents, conversation_history, document_chunks
        from app.tables.base import Base
        
        # Create all tables using shared Base
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {str(e)}")
        raise
