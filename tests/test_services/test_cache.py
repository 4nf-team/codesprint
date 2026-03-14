"""Тесты сервиса кэширования."""

import pytest

from app.services.cache import CacheService


class TestCacheService:
    """Тесты CacheService."""

    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """Тест установки и получения значения из кэша."""
        cache = CacheService()
        await cache.connect()

        try:
            await cache.set("test_key", {"value": 123})
            result = await cache.get("test_key")
            assert result == {"value": 123}
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Тест промаха кэша."""
        cache = CacheService()
        await cache.connect()

        try:
            result = await cache.get("nonexistent_key")
            assert result is None
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Тест удаления из кэша."""
        cache = CacheService()
        await cache.connect()

        try:
            await cache.set("test_key", {"value": 123})
            await cache.delete("test_key")
            result = await cache.get("test_key")
            assert result is None
        finally:
            await cache.disconnect()

    @pytest.mark.asyncio
    async def test_cache_exists(self):
        """Тест проверки существования ключа."""
        cache = CacheService()
        await cache.connect()

        try:
            await cache.set("test_key", {"value": 123})
            assert await cache.exists("test_key") is True
            assert await cache.exists("nonexistent") is False
        finally:
            await cache.disconnect()
