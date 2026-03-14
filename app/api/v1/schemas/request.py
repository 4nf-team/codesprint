"""Схемы запросов для API v1."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List


class AnalysisRequest(BaseModel):
    """
    Схема запроса на анализ изображения.

    Attributes:
        image_url: URL изображения (опционально, альтернатива загрузке файла)
        max_objects: Максимальное количество объектов для обнаружения
        confidence_threshold: Порог уверенности (0.0 - 1.0)
        include_metadata: Включать ли метаданные в ответ
    """

    image_url: Optional[str] = Field(
        None,
        description="URL изображения для анализа",
        example="https://example.com/image.jpg",
    )
    max_objects: int = Field(
        10, ge=1, le=100, description="Максимальное количество объектов для обнаружения"
    )
    confidence_threshold: float = Field(
        0.5, ge=0.0, le=1.0, description="Порог уверенности детекции"
    )
    include_metadata: bool = Field(True, description="Включать ли метаданные в ответ")

    @validator("image_url")
    def validate_url(cls, v, values):
        """Валидация URL."""
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("URL должен начинаться с http:// или https://")
        return v


class BatchAnalysisRequest(BaseModel):
    """
    Схема запроса для пакетного анализа.

    Attributes:
        urls: Список URL изображений
        max_objects: Максимальное количество объектов
        confidence_threshold: Порог уверенности
    """

    urls: List[str] = Field(
        ..., min_items=1, max_items=50, description="Список URL изображений для анализа"
    )
    max_objects: int = Field(10, ge=1, le=100)
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0)
