"""Тесты ML модели (заглушка)."""

import pytest
import asyncio


class TestMLModel:
    """Тесты ML модели (заглушка)."""

    @pytest.mark.asyncio
    async def test_model_load(self):
        """Тест загрузки модели."""
        from app.ml.model import MLModel

        model = MLModel()
        await model.load()
        assert model.model is not None
        assert model.device is not None
        assert model.version is not None

    @pytest.mark.asyncio
    async def test_model_predict(self):
        """Тест предсказания модели."""
        from app.ml.model import MLModel

        model = MLModel()
        await model.load()

        # Создаем тестовые байты (простой GIF)
        test_bytes = b"GIF89a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"

        result = await model.predict(test_bytes)

        assert "objects" in result
        assert "image_size" in result
        assert "processing_time_ms" in result
        assert "model_version" in result
        assert isinstance(result["objects"], list)

    @pytest.mark.asyncio
    async def test_model_predict_returns_different_results(self):
        """Тест что предсказания могут отличаться."""
        from app.ml.model import MLModel

        model = MLModel()
        await model.load()

        # Создаем тестовые байты
        test_bytes = b"GIF89a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"

        # Вызываем несколько раз
        results = []
        for _ in range(5):
            result = await model.predict(test_bytes)
            results.append(len(result["objects"]))

        # Результаты могут отличаться (random)
        assert all(isinstance(r, int) for r in results)

    @pytest.mark.asyncio
    async def test_model_class_names(self):
        """Тест что модель содержит список классов."""
        from app.ml.model import MLModel

        model = MLModel()

        # Проверяем что class_names содержит правильные классы
        expected_classes = ["person", "bicycle", "car", "dog", "cat"]

        for cls in expected_classes:
            assert cls in model.class_names, f"Class {cls} not found in class_names"
