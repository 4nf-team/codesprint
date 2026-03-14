"""Сервис анализа изображений."""

from typing import Dict, Any, Optional
import time
import hashlib
from datetime import datetime

from app.services.cache import CacheService
from app.services.database import DatabaseService
from app.ml.model import MLModel
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """
    Сервис для анализа изображений.

    Attributes:
        cache_service: Сервис кэширования
        db_service: Сервис базы данных
        ml_model: ML модель для анализа
    """

    def __init__(self, cache_service: CacheService, db_service: DatabaseService):
        self.cache_service = cache_service
        self.db_service = db_service
        self.ml_model = MLModel()

    def _compute_image_hash(self, image_bytes: bytes) -> str:
        """
        Вычисление хэша изображения.

        Args:
            image_bytes: Байты изображения

        Returns:
            SHA256 хэш
        """
        return hashlib.sha256(image_bytes).hexdigest()

    async def analyze_image(
        self,
        image_bytes: bytes,
        filename: Optional[str],
        user_id: Optional[str],
        content_type: str,
    ) -> Dict[str, Any]:
        """
        Полный анализ изображения.

        Args:
            image_bytes: Байты изображения
            filename: Имя файла
            user_id: ID пользователя
            content_type: MIME тип

        Returns:
            Результат анализа
        """
        start_time = time.time()

        try:
            # Вычисляем хэш изображения
            image_hash = self._compute_image_hash(image_bytes)

            # Проверяем кэш
            cache_key = self.cache_service.get_cache_key(image_hash, user_id)
            cached_result = await self.cache_service.get(cache_key)

            if cached_result:
                logger.info(f"Cache hit for image hash {image_hash}")
                cached_result["cached"] = True
                return cached_result

            logger.info(f"Cache miss for image hash {image_hash}")

            # Создаем задачу в БД
            task_id = await self.db_service.create_analysis_task(
                user_id=user_id or "anonymous", image_hash=image_hash
            )

            # Выполняем анализ через ML модель
            ml_result = await self.ml_model.predict(image_bytes)

            processing_time = (time.time() - start_time) * 1000

            # Формируем результат
            result = {
                "task_id": task_id,
                "objects": ml_result.get("objects", []),
                "metadata": {
                    "processing_time_ms": processing_time,
                    "model_version": self.ml_model.version,
                    "image_size": ml_result.get("image_size", {}),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "filename": filename,
                    "content_type": content_type,
                },
                "cached": False,
            }

            # Сохраняем в кэш
            await self.cache_service.set(cache_key, result)

            # Обновляем задачу в БД
            await self.db_service.update_task_result(
                task_id=task_id, result=result, processing_time_ms=processing_time
            )

            logger.info(
                f"Analysis completed for task {task_id}: "
                f"{len(result['objects'])} objects, {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)

            # Если задача была создана, отмечаем ошибку
            if "task_id" in locals():
                await self.db_service.update_task_error(
                    task_id=task_id, error_message=str(e)
                )

            raise

    async def analyze_batch(
        self, image_list: list, user_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Пакетный анализ изображений.

        Args:
            image_list: Список кортежей (image_bytes, filename, content_type)
            user_id: ID пользователя

        Returns:
            Агрегированный результат
        """
        results = []
        total_time = 0

        for image_bytes, filename, content_type in image_list:
            result = await self.analyze_image(
                image_bytes=image_bytes,
                filename=filename,
                user_id=user_id,
                content_type=content_type,
            )
            results.append(result)
            total_time += result["metadata"]["processing_time_ms"]

        return {
            "task_ids": [r["task_id"] for r in results],
            "total_objects": sum(len(r["objects"]) for r in results),
            "processing_time_ms": total_time,
        }
