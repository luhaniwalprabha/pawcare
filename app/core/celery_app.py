
# This file creates and configures the Celery instance.
#
# Why a separate file?
# Celery needs to be initialized before tasks are registered.
# Keeping it here avoids circular imports — tasks import from here,
# not from main.py which imports everything else.
#
# broker_url: where Celery sends tasks to (Redis)
# result_backend: where Celery stores task results (also Redis)
# task_serializer: JSON is human-readable and safe
# task_acks_late: task is only marked "done" after successful completion
#   — if worker crashes mid-task, task goes back to queue (important for reliability)
# task_reject_on_worker_lost: if worker dies, task is requeued not lost
# max_retries per task: defined on each task individually

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "pawcare",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.notifications"],  # tell Celery where to find tasks
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # worker takes one task at a time — prevents overloading

    # Retry settings — if broker is down, retry connecting
    broker_connection_retry_on_startup=True,

    # Beat schedule — periodic tasks (like daily reminders)
    beat_schedule={
        "send-appointment-reminders-daily": {
            "task": "app.tasks.notifications.send_daily_reminders",
            "schedule": 60.0 * 60 * 24,  # every 24 hours
        },
    },
)