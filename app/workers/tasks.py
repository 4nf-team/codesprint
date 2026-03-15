"""Задачи Celery для асинхронной обработки."""

import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.database import (
    AnalysisTask,
    AsyncSessionLocal,
    UserAPIKey,
)
from app.services.auth import AuthService
from app.services.cache import CacheService
from app.services.database import DatabaseService
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _process_user_rotation(
    db: AsyncSession, user_id: int, now: datetime, stats: dict
) -> None:
    """
    Обрабатывает ротацию ключей для одного пользователя.

    Args:
        db: Сессия БД
        user_id: ID пользователя
        now: Текущее время
        stats: Словарь для накопления статистики
    """
    try:
        # Получаем политику ротации пользователя через AuthService
        auth_service = AuthService(session=db)
        policy = await auth_service.get_rotation_policy(user_id, db)

        # Проверяем, включена ли авто-ротация для этой политики
        if not policy.auto_rotate:
            logger.debug("Пропускаем user_id=%d: auto_rotate=False", user_id)
            return

        # Вычисляем порог истечения
        rotate_threshold = now + timedelta(days=policy.rotate_before_days)

        # Находим активные ключи, которые скоро истекут или уже истекли
        result = await db.execute(
            select(UserAPIKey).where(
                UserAPIKey.user_id == user_id,
                UserAPIKey.is_active == True,  # noqa: E712
                or_(
                    UserAPIKey.expires_at <= rotate_threshold,
                    UserAPIKey.expires_at <= now,
                ),
            )
        )
        keys_to_rotate = result.scalars().all()

        stats["total_checked"] += len(keys_to_rotate)

        for key in keys_to_rotate:
            try:
                # Ротируем ключ с использованием политики
                new_key = await auth_service.rotate_api_key(
                    key_id=key.id,
                    key_lifetime_days=policy.key_lifetime_days,
                )

                if new_key:
                    stats["rotated"] += 1
                    stats["details"].append(
                        {
                            "key_id": key.id,
                            "user_id": user_id,
                            "success": True,
                            "error": None,
                        }
                    )
                    logger.info(
                        "Успешно ротирован ключ id=%d для user_id=%d",
                        key.id,
                        user_id,
                    )
                else:
                    stats["errors"] += 1
                    stats["details"].append(
                        {
                            "key_id": key.id,
                            "user_id": user_id,
                            "success": False,
                            "error": "rotate_api_key returned None",
                        }
                    )
                    logger.warning(
                        "Не удалось ротировать ключ id=%d для user_id=%d",
                        key.id,
                        user_id,
                    )

            except Exception as e:
                stats["errors"] += 1
                stats["details"].append(
                    {
                        "key_id": key.id,
                        "user_id": user_id,
                        "success": False,
                        "error": str(e),
                    }
                )
                logger.exception(
                    "Ошибка при ротации ключа id=%d для user_id=%d",
                    key.id,
                    user_id,
                )

    except Exception as e:
        logger.exception("Ошибка при обработке пользователя user_id=%d", user_id)


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
    logger.info("Starting analysis task %s", task_id)

    async def _analyze():
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
                logger.info("Cache hit for task %s", task_id)
                await cache_service.disconnect()
                return {**cached_result, "cached": True}

            start_time = time.time()
            processing_time = (time.time() - start_time) * 1000

            # Формируем результат (placeholder - модель ещё не подключена)
            result = {
                "task_id": task_id,
                "objects": [],
                "metadata": {
                    "processing_time_ms": processing_time,
                    "model_version": "pending",
                    "image_size": {},
                    "timestamp": datetime.now(UTC).isoformat() + "Z",
                    "filename": filename,
                    "content_type": content_type,
                    "model_status": "not_available",
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

            logger.info("Completed analysis task %s", task_id)
            return result

    try:
        return _run_async(_analyze())
    except Exception as exc:
        logger.exception("Failed analysis task %s", task_id)

        # Обновление статуса задачи в БД
        try:

            async def _update_error(error: Exception):
                async with AsyncSessionLocal() as db:
                    db_service = DatabaseService(db)
                    await db_service.update_task_error(
                        task_id=task_id, error_message=str(error)
                    )

            _run_async(_update_error(exc))
        except Exception:
            logger.exception("Failed to update task status")

        raise self.retry(exc=exc, countdown=60)


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
    logger.info(
        "Starting batch analysis task %s with %s images", task_id, len(image_list)
    )

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
        except Exception:
            logger.exception("Failed to queue image")

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
    logger.info("Starting cleanup of tasks older than %s days", days)

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            stmt = delete(AnalysisTask).where(
                AnalysisTask.created_at < cutoff_date,
                AnalysisTask.status.in_(["completed", "failed"]),
            )

            result = await db.execute(stmt)
            await db.commit()

            deleted_count = result.rowcount
            logger.info("Cleaned up %s old tasks", deleted_count)
            return {"deleted_count": deleted_count}

    try:
        return _run_async(_cleanup())
    except Exception as exc:
        logger.exception("Cleanup failed")
        return {"error": str(exc)}


@celery_app.task(name="health_check")
def health_check() -> dict[str, Any]:
    """Health check для Celery worker'ов."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "worker": celery_app.conf.worker_name or "unknown",
    }


@celery_app.task(name="rotate_expiring_api_keys", bind=True, max_retries=3)
def rotate_expiring_api_keys(self) -> dict[str, Any]:
    """
    Периодическая задача для ротации API-ключей, которые скоро истекают.

    Запускается по расписанию (например, раз в день).
    Находит все активные ключи, у которых:
    - expires_at <= now + rotate_before_days (из политики)
    - ИЛИ expires_at <= now (просроченные)
    - И у пользователя есть политика auto_rotate=True

    Для каждого ключа:
    - Создать новый ключ через auth_service.rotate_api_key()
    - Логировать операцию

    Returns:
        Статистика: сколько ключей ротировано, сколько ошибок
    """
    logger.info("Начало задачи ротации API-ключей")

    async def _rotate_keys():
        stats = {
            "total_checked": 0,
            "rotated": 0,
            "errors": 0,
            "details": [],
        }

        async with AsyncSessionLocal() as db:
            try:
                # Получаем текущее время
                now = datetime.now(UTC)

                # Находим всех пользователей, у которых есть активные API-ключи
                result = await db.execute(
                    select(UserAPIKey.user_id)
                    .distinct()
                    .where(
                        UserAPIKey.is_active == True  # noqa: E712
                    )
                )
                user_ids = [row[0] for row in result.fetchall()]

                if not user_ids:
                    logger.info("Нет пользователей с активными API-ключами")
                    return stats

                # Для каждого пользователя проверяем политику и ротируем ключи
                # Обрабатываем пользователей пачками для избежания перегрузки
                batch_size = 50
                for i in range(0, len(user_ids), batch_size):
                    batch = user_ids[i : i + batch_size]

                    # Обрабатываем пользователей параллельно
                    tasks = [
                        _process_user_rotation(db, user_id, now, stats)
                        for user_id in batch
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)

                logger.info(
                    "Завершение задачи ротации API-ключей: checked=%d, rotated=%d, errors=%d",
                    stats["total_checked"],
                    stats["rotated"],
                    stats["errors"],
                )
                return stats

            except Exception as e:
                logger.exception("Критическая ошибка в задаче ротации API-ключей")
                raise self.retry(exc=e, countdown=60)

    try:
        return _run_async(_rotate_keys())
    except Exception as exc:
        logger.exception("Задача ротации API-ключей завершилась с ошибкой")
        return {
            "total_checked": 0,
            "rotated": 0,
            "errors": 1,
            "details": [{"error": str(exc)}],
        }
