"""Сервис кэширования на основе Redis."""

import hashlib
import json
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis

if TYPE_CHECKING:
    from redis.asyncio import Redis

from app.core.config import settings


class CacheService:
    """
    Сервис кэширования с Redis.

    Attributes:
        redis_client: Асинхронный Redis клиент
        default_ttl: TTL по умолчанию в секундах
    """

    def __init__(self):
        self.redis_client: Redis | None = None
        self.default_ttl = settings.REDIS_CACHE_TTL
        self._enabled = settings.CACHE_ENABLED

    async def connect(self):
        """Установка соединения с Redis."""
        if self._enabled:
            self.redis_client = redis.from_url(
                settings.REDIS_URL, encoding="utf-8", decode_responses=True
            )

    async def disconnect(self):
        """Закрытие соединения с Redis."""
        if self.redis_client:
            await self.redis_client.close()

    def _generate_key(self, prefix: str, data: Any) -> str:
        """
        Генерация ключа кэша на основе данных.

        Args:
            prefix: Префикс ключа
            data: Данные для хэширования

        Returns:
            Ключ кэша
        """
        if isinstance(data, bytes):
            hash_input = data
        else:
            hash_input = json.dumps(data, sort_keys=True).encode()

        hash_digest = hashlib.sha256(hash_input).hexdigest()
        return f"{prefix}:{hash_digest}"

    async def get(self, key: str) -> Any | None:
        """
        Получение значения из кэша.

        Args:
            key: Ключ кэша

        Returns:
            Значение или None если не найдено
        """
        if not self._enabled or not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)
        except redis.RedisError:
            # Логировать ошибку
            return None
        else:
            if value:
                return json.loads(value)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Установка значения в кэш.

        Args:
            key: Ключ кэша
            value: Значение для сохранения
            ttl: TTL в секундах

        Returns:
            True если успешно
        """
        if not self._enabled or not self.redis_client:
            return False

        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value)
            await self.redis_client.setex(key, ttl, serialized)
        except redis.RedisError:
            # Логировать ошибку
            return False
        else:
            return True

    async def delete(self, key: str) -> bool:
        """
        Удаление ключа из кэша.

        Args:
            key: Ключ для удаления

        Returns:
            True если ключ был удален
        """
        if not self._enabled or not self.redis_client:
            return False

        try:
            result = await self.redis_client.delete(key)
        except redis.RedisError:
            return False
        else:
            return result > 0

    async def exists(self, key: str) -> bool:
        """
        Проверка существования ключа.

        Args:
            key: Ключ для проверки

        Returns:
            True если ключ существует
        """
        if not self._enabled or not self.redis_client:
            return False

        try:
            result = await self.redis_client.exists(key)
        except redis.RedisError:
            return False
        else:
            return result > 0

    async def clear(self):
        """Очистка всего кэша."""
        if self._enabled and self.redis_client:
            with suppress(redis.RedisError):
                await self.redis_client.flushdb()

    def get_cache_key(self, image_hash: str, user_id: str | None = None) -> str:
        """
        Генерация ключа кэша для анализа изображения.

        Args:
            image_hash: Хэш изображения
            user_id: ID пользователя (опционально)

        Returns:
            Ключ кэша
        """
        prefix = "analysis"
        if user_id:
            return f"{prefix}:user:{user_id}:{image_hash}"
        return f"{prefix}:{image_hash}"
