"""
Celery tasks
"""
# Import all task modules so Celery can discover them
from app.tasks import whatsapp_tasks
from app.tasks import webhook_tasks
from app.tasks import onboarding_tasks

__all__ = [
    "whatsapp_tasks",
    "webhook_tasks",
    "onboarding_tasks",
]

