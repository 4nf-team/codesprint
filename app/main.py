"""
FastAPI приложение для анализа изображений.
Точка входа и конфигурация сервиса.
"""

from contextlib import asynccontextmanager

from celery.exceptions import CeleryError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.endpoints import analysis, health, metrics
from app.core.config import settings
from app.core.logging import configure_logging
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.prometheus import PrometheusMiddleware
from app.services.cache import CacheService
from app.services.database import DatabaseService, close_db, init_db
from app.workers.celery_app import celery_app

# Инициализация сервисов
cache_service = CacheService()
db_service = DatabaseService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Выполняется при запуске и остановке приложения.
    """
    # Startup
    configure_logging()

    # Инициализация базы данных
    await init_db()
    app.state.db_service = db_service

    # Подключение к Redis
    await cache_service.connect()
    app.state.cache_service = cache_service

    # Проверка доступности Celery
    try:
        # Простая проверка - пытаемся получить информацию о worker'ах
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            app.state.celery_available = True
        else:
            app.state.celery_available = False
    except CeleryError:
        app.state.celery_available = False

    yield

    # Shutdown
    await cache_service.disconnect()
    await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="High-performance image analysis API service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip сжатие
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted Hosts (в production нужно ограничить)
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
    )

# Кастомные middleware
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

# Роутеры API
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])


@app.get("/")
async def root():
    """Корневой эндпоинт с информацией о сервисе."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None,
    }
