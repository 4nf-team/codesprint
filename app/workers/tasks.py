"""Задачи Celery для асинхронной обработки."""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.ml.model import MLModel
from app.models.database import AsyncSessionLocal

logger = get_logger(__name__)


# Инициализация Celery app
from app.workers.celery_app import celery_app


def _run_async(coro):
    """Запуск асинхронной функции в синхронном контексте Celery."""
    return asyncio.run(coro)


@celery_app.task(
    name="analyze_image_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def analyze_image_task(
    self, image_bytes: bytes, filename: str, user_id: str, content_type: str
) -> dict[str, Any]:
    """
    Задача анализа изображения.

    Args:
        self: Celery task
        image_bytes: Байты изображения
        filename: Имя файла
        user_id: ID пользователя
        content_type: MIME тип

    Returns:
        Результат анализа
    """
    task_id = self.request.id or str(uuid.uuid4())
    logger.info(f"Starting analysis task {task_id}")

    async def _analyze():
        from app.services.cache import CacheService
        from app.services.database import DatabaseService

        async with AsyncSessionLocal() as db:
            cache_service = CacheService()
            await cache_service.connect()
            db_service = DatabaseService(db)

            # Вычисляем хэш изображения
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            # Проверяем кэш
            cache_key = cache_service.get_cache_key(image_hash, user_id)
            cached_result = await cache_service.get(cache_key)

            if cached_result:
                logger.info(f"Cache hit for task {task_id}")
                await cache_service.disconnect()
                return {**cached_result, "cached": True}

            # Загружаем ML модель и выполняем анализ
            ml_model = MLModel()
            await ml_model.load()

            import time

            start_time = time.time()
            ml_result = await ml_model.predict(image_bytes)
            processing_time = (time.time() - start_time) * 1000

            # Формируем результат
            result = {
                "task_id": task_id,
                "objects": ml_result.get("objects", []),
                "metadata": {
                    "processing_time_ms": processing_time,
                    "model_version": ml_model.version,
                    "image_size": ml_result.get("image_size", {}),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "filename": filename,
                    "content_type": content_type,
                },
                "cached": False,
            }

            # Сохраняем в кэш
            await cache_service.set(cache_key, result)
            await cache_service.disconnect()

            # Обновляем задачу в БД
            await db_service.update_task_result(
                task_id=task_id, result=result, processing_time_ms=processing_time
            )

            logger.info(f"Completed analysis task {task_id}")
            return result

    try:
        return _run_async(_analyze())
    except Exception as task_exc:
        logger.error(f"Failed analysis task {task_id}: {task_exc}", exc_info=True)

        # Обновление статуса задачи в БД
        try:

            async def _update_error():
                from app.services.database import DatabaseService

                async with AsyncSessionLocal() as db:
                    db_service = DatabaseService(db)
                    await db_service.update_task_error(
                        task_id=task_id, error_message=str(task_exc)
                    )

            _run_async(_update_error())
        except Exception as db_exc:
            logger.error(f"Failed to update task status: {db_exc}")

        raise self.retry(exc=task_exc, countdown=60)


@celery_app.task(
    name="batch_analyze_task",
    bind=True,
    max_retries=2,
)
def batch_analyze_task(self, image_list: list[tuple], user_id: str) -> dict[str, Any]:
    """
    Пакетная задача анализа.

    Args:
        self: Celery task
        image_list: Список кортежей (bytes, filename, content_type)
        user_id: ID пользователя

    Returns:
        Агрегированный результат
    """
    task_id = self.request.id or str(uuid.uuid4())
    logger.info(f"Starting batch analysis task {task_id} with {len(image_list)} images")

    results = []

    for image_bytes, filename, content_type in image_list:
        try:
            result = analyze_image_task.delay(
                image_bytes=image_bytes,
                filename=filename,
                user_id=user_id,
                content_type=content_type,
            )
            results.append(result.id)
        except Exception as e:
            logger.error(f"Failed to queue image {filename}: {e}")

    return {
        "batch_id": task_id,
        "task_ids": results,
        "total_images": len(image_list),
    }


@celery_app.task(name="cleanup_old_tasks")
def cleanup_old_tasks(days: int = 30) -> dict[str, Any]:
    """
    Очистка старых задач из базы данных.

    Args:
        days: Количество дней для хранения
    """
    logger.info(f"Starting cleanup of tasks older than {days} days")

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import delete
            from app.models.database import AnalysisTask

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            stmt = delete(AnalysisTask).where(
                AnalysisTask.created_at < cutoff_date,
                AnalysisTask.status.in_(["completed", "failed"]),
            )

            result = await db.execute(stmt)
            await db.commit()

            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old tasks")
            return {"deleted_count": deleted_count}

    try:
        return _run_async(_cleanup())
    except Exception as exc:
        logger.error(f"Cleanup failed: {exc}", exc_info=True)
        return {"error": str(exc)}


@celery_app.task(name="health_check")
def health_check() -> dict[str, Any]:
    """Health check для Celery worker'ов."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "worker": celery_app.conf.worker_name or "unknown",
    }
