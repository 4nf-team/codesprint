"""Pytest конфигурация и фикстуры."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import AsyncSessionLocal, init_db


@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator:
    """
    Фикстура для тестовой сессии БД.

    В реальном проекте нужно использовать отдельную тестовую БД.
    """
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client() -> TestClient:
    """
    Фикстура для HTTP клиента FastAPI.

    Returns:
        TestClient для тестирования API
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_image_bytes() -> bytes:
    """
    Фикстура с примером изображения в байтах.

    Returns:
        Байты тестового изображения
    """
    # Создаем простое тестовое изображение 100x100 красного цвета
    import io

    from PIL import Image

    image = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()
