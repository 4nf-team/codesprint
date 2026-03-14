"""Модуль безопасности и аутентификации."""

import hmac
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class User:
    """Модель пользователя."""

    user_id: str
    api_key: str
    rate_limit: int = 40  # запросов в минуту
    is_active: bool = True


class APIKeyAuth:
    """
    Сервис аутентификации по API ключу.

    Attributes:
        secret_key: Секретный ключ для подписи
        api_keys: Словарь API ключей и соответствующих пользователей
    """

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        # В реальном приложении это будет из БД
        self._users: dict[str, User] = {}

    def verify_key(self, api_key: str) -> User | None:
        """
        Проверка API ключа.

        Args:
            api_key: API ключ для проверки

        Returns:
            User если ключ валиден, иначе None
        """
        # В реальном приложении проверка по БД с хэшированием
        for user in self._users.values():
            if hmac.compare_digest(api_key, user.api_key):
                return user
        return None

    def add_user(self, user: User) -> None:
        """Добавление пользователя (для тестов/разработки)."""
        self._users[user.user_id] = user

    def remove_user(self, user_id: str) -> None:
        """Удаление пользователя."""
        if user_id in self._users:
            del self._users[user_id]


class RateLimiter:
    """
    Простой rate limiter на основе алгоритма token bucket.
    В production использовать Redis для распределенного limiting.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, Any]] = {}

    def is_allowed(self, key: str, limit: int, period: int = 60) -> bool:
        """
        Проверка rate limit.

        Args:
            key: Ключ (например, IP или user_id)
            limit: Максимальное количество запросов
            period: Период в секундах

        Returns:
            True если запрос разрешен
        """
        now = time.time()

        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": limit,
                "last_update": now,
                "limit": limit,
                "period": period,
            }

        bucket = self._buckets[key]

        # Восстановление токенов
        time_passed = now - bucket["last_update"]
        tokens_to_add = int(time_passed * (bucket["limit"] / bucket["period"]))

        if tokens_to_add > 0:
            bucket["tokens"] = min(bucket["limit"], bucket["tokens"] + tokens_to_add)
            bucket["last_update"] = now

        # Проверка доступности токена
        if bucket["tokens"] > 0:
            bucket["tokens"] -= 1
            return True

        return False

    def reset(self, key: str | None = None) -> None:
        """Сброс счетчика."""
        if key:
            self._buckets.pop(key, None)
        else:
            self._buckets.clear()
