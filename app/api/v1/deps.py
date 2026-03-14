"""Зависимости для API v1."""

from typing import Any

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import APIKeyAuth, User

# Инициализация rate limiter
limiter = Limiter(key_func=get_remote_address)

# Глобальный экземпляр APIKeyAuth
api_key_auth = APIKeyAuth(settings.API_KEY)
# Добавляем тестового пользователя для development
api_key_auth.add_user(
    User(user_id="test_user", api_key="changeme", rate_limit=100, is_active=True)
)


class RateLimitService:
    """Сервис rate limiting."""

    def __init__(self):
        self.limiter = limiter

    async def check(self):
        """Проверка rate limit."""
        # В реальной реализации будет проверка через limiter
        # Для заглушки просто пропускаем


async def get_current_user(request: Request) -> dict[str, Any]:
    """
    Получение текущего пользователя по API ключу.

    Args:
        request: FastAPI request объект

    Returns:
        Информация о пользователе

    Raises:
        HTTPException: Если аутентификация не удалась
    """
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    user = api_key_auth.verify_key(api_key)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "user_id": user.user_id,
        "rate_limit": user.rate_limit,
        "is_active": user.is_active,
    }


def get_rate_limiter() -> RateLimitService:
    """Получение сервиса rate limiting."""
    return RateLimitService()
