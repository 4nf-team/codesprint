"""Health check эндпоинт."""

from fastapi import APIRouter, Depends, Request
from redis import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.database import get_db
from app.services.cache import CacheService
from app.services.database import DatabaseService

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Проверка здоровья сервиса и его зависимостей.

    Returns:
        Статус здоровья сервиса
    """
    # Проверяем подключение к БД
    db_service = DatabaseService(db)
    try:
        await db_service.check_connection()
        db_status = True
    except (SQLAlchemyError, OSError):
        db_status = False
        logger.exception("Database health check failed")

    # Проверяем Redis кэш
    cache_status = False
    try:
        cache_service = CacheService()
        await cache_service.connect()
        if cache_service.redis_client:
            await cache_service.redis_client.ping()
            cache_status = True
        await cache_service.disconnect()
    except (RedisError, OSError):
        cache_status = False
        logger.exception("Cache health check failed")

    # Проверяем ML модель
    model_status = False
    try:
        if hasattr(request.app.state, "ml_model") and request.app.state.ml_model:
            model_status = True
    except (AttributeError, TypeError):
        model_status = False
        logger.exception("Model health check failed")

    # Проверяем Celery
    celery_status = False
    try:
        if hasattr(request.app.state, "celery_available"):
            celery_status = request.app.state.celery_available
    except (AttributeError, TypeError):
        celery_status = False
        logger.exception("Celery health check failed")

    all_healthy = db_status and cache_status

    return {
        "status": "ok" if all_healthy else "degraded",
        "version": "1.0.0",
        "services": {
            "database": db_status,
            "cache": cache_status,
            "model": model_status,
            "queue": celery_status,
        },
    }


@router.get("/ready")
async def readiness_check(_request: Request, db: AsyncSession = Depends(get_db)):
    """
    Проверка готовности сервиса принимать трафик.

    Returns:
        Статус готовности
    """
    # Проверяем БД
    db_service = DatabaseService(db)
    try:
        await db_service.check_connection()
    except (SQLAlchemyError, OSError):
        logger.exception("Readiness check failed")
        return {"ready": False, "reason": "database unavailable"}

    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """
    Liveness probe для Kubernetes.

    Returns:
        Статус alive
    """
    return {"alive": True}
