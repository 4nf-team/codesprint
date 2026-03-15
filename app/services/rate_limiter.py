"""Распределенный rate limiter на основе Redis с Lua-скриптами."""

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import redis.asyncio as redis
from redis.asyncio import Redis
from sqlalchemy import select

from app.core.logging import get_logger
from app.models.database import RateLimitConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class RateLimitResult:
    """Результат проверки rate limit."""

    is_allowed: bool
    remaining: int
    reset_after: float  # секунды до сброса
    limit: int
    retry_after: float | None = None


class RedisRateLimiter:
    """
    Redis Rate Limiter с sliding window algorithm через Lua-скрипты.

    Использует sorted set для хранения запросов с timestamp как score.
    Обеспечивает атомарность операций через Lua-скрипты.

    Attributes:
        redis: Асинхронный Redis клиент
        lua_script: Lua-скрипт для атомарной проверки и обновления
    """

    def __init__(self, redis_client: Redis):
        """
        Инициализация rate limiter.

        Args:
            redis_client: Асинхронный Redis клиент
        """
        self.redis = redis_client
        # Lua-скрипт для проверки и обновления лимита (sliding window)
        self.lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local request_id = ARGV[4]

        -- Удаляем старые записи вне окна
        redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

        -- Считаем текущие запросы в окне
        local count = redis.call('ZCARD', key)

        if count < limit then
            -- Добавляем новый запрос
            redis.call('ZADD', key, now, request_id)
            redis.call('EXPIRE', key, window)
            return 1  -- разрешено
        else
            -- Получаем время самого старого запроса в окне
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            if oldest and #oldest >= 2 then
                local oldest_time = tonumber(oldest[2])
                local retry_after = oldest_time + window - now
                return 2  -- запрещено, возвращаем retry_after
            end
            return 0  -- запрещено
        end
        """

    async def check_rate_limit(
        self,
        identifier: str,  # user_id или IP
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """
        Проверка rate limit для заданного идентификатора и эндпоинта.

        Args:
            identifier: Идентификатор (user_id или IP)
            endpoint: Эндпоинт API
            limit: Максимальное количество запросов
            window_seconds: Окно в секундах

        Returns:
            RateLimitResult с информацией о лимите
        """
        # Генерация уникального ID запроса
        request_id = str(uuid.uuid4())
        now = time.time()
        key = f"rate_limit:{identifier}:{endpoint}"

        try:
            # Выполнение Lua-скрипта
            result = await self.redis.eval(
                self.lua_script,
                keys=[key],
                args=[now, window_seconds, limit, request_id],
            )

            # Получаем текущее количество запросов
            count = await self.redis.zcard(key)
            remaining = max(0, limit - count)

            if result == 1:  # Разрешено
                return RateLimitResult(
                    is_allowed=True,
                    remaining=remaining,
                    reset_after=window_seconds,
                    limit=limit,
                )
            else:  # Запрещено
                # Получаем время самого старого запроса для расчета retry_after
                oldest = await self.redis.zrange(key, 0, 0, withscores=True)
                retry_after = None
                if oldest:
                    oldest_time = oldest[0][1] if len(oldest[0]) > 1 else now
                    retry_after = max(0, oldest_time + window_seconds - now)

                return RateLimitResult(
                    is_allowed=False,
                    remaining=0,
                    reset_after=window_seconds,
                    limit=limit,
                    retry_after=retry_after,
                )

        except redis.RedisError as e:
            logger.error(
                "Redis error during rate limit check",
                extra={"identifier": identifier, "endpoint": endpoint, "error": str(e)},
            )
            # При ошибке Redis используем стратегию fail-open/fail-closed из конфига
            from app.core.config import settings

            is_allowed = settings.RATE_LIMIT_FAIL_OPEN

            return RateLimitResult(
                is_allowed=is_allowed,
                remaining=0 if not is_allowed else limit,
                reset_after=window_seconds,
                limit=limit,
                retry_after=None if is_allowed else window_seconds,
            )


class RateLimitService:
    """
    Сервис управления rate limiting.

    Интегрируется с базой данных для получения конфигураций
    и с Redis для распределенной проверки лимитов.

    Attributes:
        redis: Асинхронный Redis клиент
        limiter: RedisRateLimiter для атомарных операций
        db_session_factory: Фабрика сессий БД
    """

    def __init__(self, redis_client: Redis, db_session_factory):
        """
        Инициализация сервиса.

        Args:
            redis_client: Асинхронный Redis клиент
            db_session_factory: Фабрика для создания сессий БД
        """
        self.redis = redis_client
        self.limiter = RedisRateLimiter(redis_client)
        self.db_session_factory = db_session_factory

    async def get_limit_for_user(self, user_id: int, endpoint: str) -> tuple[int, int]:
        """
        Получение лимитов для пользователя из конфигурации.

        Args:
            user_id: ID пользователя
            endpoint: Эндпоинт API

        Returns:
            Кортеж (requests_per_minute, requests_per_hour)
        """
        async with self.db_session_factory() as session:
            try:
                # Ищем конфиг по паттерну эндпоинта
                stmt = select(RateLimitConfig).where(
                    RateLimitConfig.endpoint_pattern == endpoint
                )
                result = await session.execute(stmt)
                config = result.scalar_one_or_none()

                if config:
                    return (config.requests_per_minute, config.requests_per_hour)

                # Ищем глобальный дефолтный конфиг
                stmt = (
                    select(RateLimitConfig)
                    .where(RateLimitConfig.is_global == True)
                    .limit(1)
                )
                result = await session.execute(stmt)
                global_config = result.scalar_one_or_none()

                if global_config:
                    return (
                        global_config.requests_per_minute,
                        global_config.requests_per_hour,
                    )

                # Дефолтные значения если нет конфигов
                return (100, 1000)

            except Exception as e:
                logger.error(
                    "Error fetching rate limit config",
                    extra={"user_id": user_id, "endpoint": endpoint, "error": str(e)},
                )
                return (100, 1000)

    async def check(
        self, user_id: Optional[int], ip_address: str, endpoint: str
    ) -> RateLimitResult:
        """
        Проверка rate limit с приоритетом user-specific > global.

        Args:
            user_id: ID пользователя (None для анонимных)
            ip_address: IP адрес клиента
            endpoint: Эндпоинт API

        Returns:
            RateLimitResult с информацией о лимите
        """
        # Определяем лимиты в зависимости от наличия user_id
        if user_id is not None:
            # Получаем лимиты для пользователя
            per_minute, per_hour = await self.get_limit_for_user(user_id, endpoint)
        else:
            # Для анонимных используем IP-based глобальные лимиты
            per_minute, per_hour = await self.get_limit_for_user(0, endpoint)

        # Проверяем по user_id если есть
        if user_id is not None:
            user_key = f"user:{user_id}"
            result = await self.limiter.check_rate_limit(
                identifier=user_key,
                endpoint=endpoint,
                limit=per_minute,
                window_seconds=60,
            )

            if not result.is_allowed:
                # Логируем превышение лимита
                logger.warning(
                    "Rate limit exceeded by user",
                    extra={
                        "user_id": user_id,
                        "endpoint": endpoint,
                        "limit": per_minute,
                        "remaining": result.remaining,
                    },
                )
                return result

        # Проверяем по IP (всегда)
        ip_key = f"ip:{ip_address}"
        ip_result = await self.limiter.check_rate_limit(
            identifier=ip_key, endpoint=endpoint, limit=per_minute, window_seconds=60
        )

        if not ip_result.is_allowed:
            logger.warning(
                "Rate limit exceeded by IP",
                extra={
                    "ip_address": ip_address,
                    "endpoint": endpoint,
                    "limit": per_minute,
                    "remaining": ip_result.remaining,
                },
            )

        return ip_result

    async def get_usage_stats(
        self, user_id: int, endpoint: Optional[str] = None
    ) -> dict:
        """
        Получение статистики использования для пользователя.

        Args:
            user_id: ID пользователя
            endpoint: Эндпоинт (если None, то по всем)

        Returns:
            Словарь со статистикой
        """
        stats = {"user_id": user_id, "endpoints": {}}

        try:
            # Определяем ключи для поиска
            if endpoint:
                patterns = [f"rate_limit:user:{user_id}:{endpoint}"]
            else:
                # Получаем все ключи пользователя
                scan_pattern = f"rate_limit:user:{user_id}:*"
                keys = []
                cursor = 0
                while True:
                    cursor, batch = await self.redis.scan(
                        cursor=cursor, match=scan_pattern, count=100
                    )
                    keys.extend(batch)
                    if cursor == 0:
                        break
                patterns = keys

            # Собираем статистику по каждому ключу
            for pattern in patterns:
                count = await self.redis.zcard(pattern)
                if count > 0:
                    # Извлекаем endpoint из ключа
                    parts = pattern.split(":")
                    if len(parts) >= 5:
                        ep = ":".join(parts[4:])  # для эндпоинтов с :
                    else:
                        ep = parts[-1]

                    ttl = await self.redis.ttl(pattern)

                    stats["endpoints"][ep] = {
                        "current_requests": count,
                        "reset_in_seconds": ttl if ttl > 0 else 0,
                    }

        except redis.RedisError as e:
            logger.error(
                "Error getting usage stats", extra={"user_id": user_id, "error": str(e)}
            )

        return stats


# Глобальный синглтон для Redis клиента
_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """
    Получает глобальный экземпляр Redis клиента.

    Returns:
        Асинхронный Redis клиент
    """
    global _redis_client  # noqa: PLW0603

    if _redis_client is None:
        from app.core.config import settings

        _redis_client = redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )

    return _redis_client


async def get_rate_limit_service() -> RateLimitService:
    """
    Dependency provider для FastAPI.

    Returns:
        Экземпляр RateLimitService
    """
    from app.services.database import AsyncSessionLocal

    # Используем глобальный синглтон Redis клиента
    redis_client = get_redis_client()

    # Возвращаем сервис с фабрикой сессий
    return RateLimitService(redis_client, lambda: AsyncSessionLocal())
