"""Зависимости для API v1."""

from typing import Any

from fastapi import Depends, HTTPException, Request

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AsyncSessionLocal
from app.services.auth import AuthService
from app.services.rate_limiter import (
    RateLimitResult,
    RateLimitService,
    get_rate_limit_service,
)


async def get_db_session():
    """Получение сессии БД для зависимостей FastAPI."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    request: Request, db_session: AsyncSessionLocal = Depends(get_db_session)
) -> dict[str, Any]:
    """
    Получение текущего пользователя по API ключу или JWT токену.

    Поддерживает два метода аутентификации:
    1. JWT токен через заголовок Authorization: Bearer <token>
    2. API ключ через заголовок X-API-Key

    Args:
        request: FastAPI request объект
        db_session: Сессия БД

    Returns:
        Информация о пользователе

    Raises:
        HTTPException: Если аутентификация не удалась
    """
    # Создаем экземпляр сервиса аутентификации с сессией БД
    auth_service = AuthService(session=db_session)

    # Проверяем JWT токен (Authorization: Bearer)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        user = await auth_service.verify_token(token)
        if user:
            # Получаем rate_limit из политики пользователя (с той же сессией)
            policy = await auth_service.get_rotation_policy(user.id, db_session)
            return {
                "user_id": user.id,
                "rate_limit": policy.key_lifetime_days
                * 10,  # Пример: 90 дней = 900 запросов/день
                "is_active": user.is_active,
            }

    # Проверяем API ключ (X-API-Key)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = await auth_service.verify_api_key(api_key)
        if user:
            # Получаем rate_limit из политики пользователя (с той же сессией)
            policy = await auth_service.get_rotation_policy(user.id, db_session)
            return {
                "user_id": user.id,
                "rate_limit": policy.key_lifetime_days * 10,
                "is_active": user.is_active,
            }

    raise HTTPException(status_code=401, detail="Не авторизован")


async def rate_limit_dependency(
    request: Request,
    user: dict = Depends(get_current_user),
    rate_limit_service: RateLimitService = Depends(get_rate_limit_service),
) -> RateLimitResult:
    """
    FastAPI dependency для rate limiting.

    Args:
        request: FastAPI Request объект
        user: Информация о пользователе
        rate_limit_service: Сервис rate limiting

    Returns:
        RateLimitResult

    Raises:
        HTTPException: Если лимит превышен
    """
    # Получаем эндпоинт
    endpoint = request.url.path

    # Получаем IP адрес
    ip_address = request.client.host if request.client else "127.0.0.1"

    # Получаем user_id
    user_id = user.get("user_id")

    # Проверяем лимит
    result = await rate_limit_service.check(
        user_id=user_id, ip_address=ip_address, endpoint=endpoint
    )

    if not result.is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests",
            headers={
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(int(result.reset_after)),
                "Retry-After": str(int(result.retry_after))
                if result.retry_after
                else "1",
            },
        )

    return result


async def get_auth_service(db: AsyncSession = Depends(get_db_session)) -> AuthService:
    """
    Зависимость FastAPI для получения AuthService с сессией БД.

    Args:
        db: Сессия БД (автоматически предоставляется через get_db_session)

    Returns:
        Экземпляр AuthService
    """
    return AuthService(session=db)
