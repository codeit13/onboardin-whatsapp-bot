"""
Celery application configuration
"""
import logging
from celery import Celery
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create Celery app
celery_app = Celery(
    "onboarding",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.whatsapp_tasks",
        "app.tasks.webhook_tasks",
        "app.tasks.onboarding_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Optional: Configure task routes
# Note: whatsapp_tasks will use default "celery" queue
celery_app.conf.task_routes = {
    "app.tasks.webhook_tasks.*": {"queue": "webhooks"},
    "app.tasks.onboarding_tasks.*": {"queue": "onboarding"},
    # whatsapp_tasks uses default queue (no routing needed)
}


@celery_app.signals.worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize services when Celery worker process starts
    This ensures database and RAG services are available in the worker
    """
    try:
        logger.info("🔧 Initializing Celery worker process...")
        
        # Initialize database
        from app.core.database import init_database
        init_database()
        logger.info("✅ Database initialized in Celery worker")
        
        # Initialize RAG services (embedding model and vector store)
        try:
            from app.services.rag.singletons import initialize_rag_services
            initialize_rag_services()
            logger.info("✅ RAG services initialized in Celery worker")
        except Exception as e:
            logger.warning(f"⚠️  RAG services initialization warning: {e}")
            # Don't fail worker startup - will be initialized on first task if needed
        
        logger.info("✅ Celery worker process initialization complete")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Celery worker process: {e}", exc_info=True)
        # Don't raise - let tasks handle initialization if needed

