"""Конфигурация Celery для асинхронных задач."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Создание Celery приложения
celery_app = Celery(
    "image_analysis",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Конфигурация Celery
celery_app.conf.update(
    # Общие настройки
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Настройки очередей
    task_queues={
        "analysis": {"exchange": "analysis", "routing_key": "analysis"},
        "batch": {"exchange": "batch", "routing_key": "batch"},
        "maintenance": {"exchange": "maintenance", "routing_key": "maintenance"},
    },
    task_routes={
        "app.workers.tasks.analyze_image_task": {"queue": "analysis"},
        "app.workers.tasks.batch_analyze_task": {"queue": "batch"},
        "app.workers.tasks.cleanup_old_tasks": {"queue": "maintenance"},
        "app.workers.tasks.rotate_expiring_api_keys": {"queue": "maintenance"},
    },
    # Настройки worker'ов
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=500000,  # 500MB
    # Настройки задач
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    # Настройки result backend
    result_expires=3600,  # 1 час
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    # Мониторинг
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Периодические задачи (beat)
celery_app.conf.beat_schedule = {
    "cleanup-old-tasks": {
        "task": "app.workers.tasks.cleanup_old_tasks",
        "schedule": crontab(hour=2, minute=0),  # Каждый день в 2:00
    },
    "health-check": {
        "task": "app.workers.tasks.health_check",
        "schedule": 60.0,  # Каждую минуту
    },
    "rotate-api-keys-daily": {
        "task": "rotate_expiring_api_keys",
        "schedule": crontab(hour=2, minute=0),  # Каждый день в 2:00
    },
}


if __name__ == "__main__":
    celery_app.start()
