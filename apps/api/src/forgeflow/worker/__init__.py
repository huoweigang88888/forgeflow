"""
ForgeFlow AI - Celery Application & Scheduled Tasks.

Async task queue for:
- Email notifications
- Batch embedding generation
- Data retention purging
- Report generation

Usage:
    celery -A forgeflow.worker.celery_app worker --loglevel=info
    celery -A forgeflow.worker.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab

from forgeflow.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forgeflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["forgeflow.worker.tasks"],
)

# ------------------------------------------------------------------
# Celery Configuration
# ------------------------------------------------------------------

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=300,  # 5 minutes soft limit
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,  # Fair dispatch
    result_expires=3600,  # Results expire after 1 hour
)

# ------------------------------------------------------------------
# Scheduled Tasks (Celery Beat)
# ------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    # Batch embedding update: every 30 minutes
    "batch-update-embeddings": {
        "task": "forgeflow.worker.tasks.batch_update_embeddings",
        "schedule": crontab(minute="*/30"),
        "options": {"expires": 1500},  # 25 min
    },
    # Data retention purge: daily at 3:00 AM UTC
    "data-retention-purge": {
        "task": "forgeflow.worker.tasks.purge_expired_data",
        "schedule": crontab(hour=3, minute=17),
        "options": {"expires": 3600},
    },
    # Cost report generation: daily at 2:00 AM UTC
    "daily-cost-report": {
        "task": "forgeflow.worker.tasks.generate_daily_cost_report",
        "schedule": crontab(hour=2, minute=7),
        "options": {"expires": 1800},
    },
    # Health check: every 5 minutes
    "health-check": {
        "task": "forgeflow.worker.tasks.system_health_check",
        "schedule": crontab(minute="*/5"),
        "options": {"expires": 240},
    },
}
