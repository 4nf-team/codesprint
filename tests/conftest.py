"""Pytest конфигурация и фикстуры."""

import asyncio
import io
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.database import AsyncSessionLocal, init_db
from app.services.auth import AuthService


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
    image = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture(scope="function")
async def test_api_key() -> AsyncGenerator[str, None]:
    """
    Фикстура для создания тестового API ключа.

    Создает тестового пользователя и API ключ в БД для каждого теста.
    Возвращает API ключ для использования в заголовках аутентификации.
    Очищает данные после завершения теста.

    Yields:
        API ключ для аутентификации

    Example:
        async def test_something(test_api_key):
            api_key = test_api_key  # Получение ключа
            # ... тест ...
    """
    await init_db()
    test_user_id = None

    async with AsyncSessionLocal() as session:
        auth_service = AuthService(session)
        user = await auth_service.create_user(
            telegram_id=123456789, first_name="Test", last_name="User"
        )
        test_user_id = user.id
        api_key = await auth_service.create_api_key(user.id, name="test_key")
        await session.commit()

    # Возвращаем ключ для использования в тесте
    yield api_key

    # Очистка после теста
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete

        from app.models.database import APIKeyRotationPolicy, User, UserAPIKey

        # Удаляем тестовые данные
        await session.execute(
            delete(UserAPIKey).where(UserAPIKey.user_id == test_user_id)
        )
        await session.execute(
            delete(APIKeyRotationPolicy).where(
                APIKeyRotationPolicy.user_id == test_user_id
            )
        )
        await session.execute(delete(User).where(User.id == test_user_id))
        await session.commit()
