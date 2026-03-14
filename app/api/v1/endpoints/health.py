"""Health check эндпоинт."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.services.cache import CacheService
from app.services.database import DatabaseService

router = APIRouter()


@router.get("/health")
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
    except Exception as exc:
        db_status = False
        print(f"Database health check failed: {exc}")

    # Проверяем Redis кэш
    cache_status = False
    try:
        cache_service = CacheService()
        await cache_service.connect()
        if cache_service.redis_client:
            await cache_service.redis_client.ping()
            cache_status = True
        await cache_service.disconnect()
    except Exception as exc:
        cache_status = False
        print(f"Cache health check failed: {exc}")

    # Проверяем ML модель
    model_status = False
    try:
        if hasattr(request.app.state, "ml_model") and request.app.state.ml_model:
            model_status = True
    except Exception as exc:
        model_status = False
        print(f"Model health check failed: {exc}")

    # Проверяем Celery
    celery_status = False
    try:
        if hasattr(request.app.state, "celery_available"):
            celery_status = request.app.state.celery_available
    except Exception as exc:
        celery_status = False
        print(f"Celery health check failed: {exc}")

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


@router.get("/health/ready")
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
    except Exception as exc:
        return {"ready": False, "reason": f"database unavailable: {exc}"}

    return {"ready": True}


@router.get("/health/live")
async def liveness_check():
    """
    Liveness probe для Kubernetes.

    Returns:
        Статус alive
    """
    return {"alive": True}
