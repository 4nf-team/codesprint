"""Схемы ответов для API v1."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    """Статус задачи анализа."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BoundingBox(BaseModel):
    """Bounding box объекта."""

    x: float = Field(..., description="Координата X левого верхнего угла")
    y: float = Field(..., description="Координата Y левого верхнего угла")
    width: float = Field(..., description="Ширина bounding box")
    height: float = Field(..., description="Высота bounding box")


class DetectedObject(BaseModel):
    """
    Обнаруженный объект.

    Attributes:
        label: Название класса объекта
        confidence: Уверенность обнаружения (0.0 - 1.0)
        bbox: Bounding box объекта
    """

    label: str = Field(..., description="Класс объекта")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность")
    bbox: BoundingBox = Field(..., description="Bounding box")


class AnalysisMetadata(BaseModel):
    """
    Метаданные анализа.

    Attributes:
        processing_time_ms: Время обработки в миллисекундах
        model_version: Версия использованной модели
        image_size: Размер изображения (ширина, высота)
        timestamp: Время выполнения анализа
    """

    processing_time_ms: float = Field(..., description="Время обработки (мс)")
    model_version: str = Field(..., description="Версия модели")
    image_size: dict[str, int] = Field(..., description="Размер изображения")
    timestamp: datetime = Field(..., description="Время анализа")


class AnalysisResponse(BaseModel):
    """
    Ответ на запрос анализа изображения.

    Attributes:
        task_id: ID задачи анализа
        objects: Список обнаруженных объектов
        metadata: Метаданные анализа
        cached: Была ли информация взята из кэша
    """

    task_id: str = Field(..., description="ID задачи анализа")
    objects: list[DetectedObject] = Field(
        default_factory=list, description="Обнаруженные объекты"
    )
    metadata: AnalysisMetadata = Field(..., description="Метаданные")
    cached: bool = Field(False, description="Использовался ли кэш")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "objects": [
                    {
                        "label": "person",
                        "confidence": 0.95,
                        "bbox": {
                            "x": 100.0,
                            "y": 50.0,
                            "width": 200.0,
                            "height": 300.0,
                        },
                    }
                ],
                "metadata": {
                    "processing_time_ms": 150.5,
                    "model_version": "yolov5s-v1.0",
                    "image_size": {"width": 640, "height": 480},
                    "timestamp": "2024-01-15T10:30:00Z",
                },
                "cached": False,
            }
        }


class TaskStatusResponse(BaseModel):
    """
    Ответ о статусе задачи.

    Attributes:
        task_id: ID задачи
        status: Статус задачи
        result: Результат (если завершена)
        message: Сообщение о статусе
    """

    task_id: str = Field(..., description="ID задачи")
    status: TaskStatus = Field(..., description="Статус задачи")
    result: dict[str, Any] | None = Field(None, description="Результат анализа")
    message: str | None = Field(None, description="Сообщение о статусе")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "result": {
                    "task_id": "550e8400-e29b-41d4-a716-446655440000",
                    "objects": [],
                    "metadata": {
                        "processing_time_ms": 150.5,
                        "model_version": "yolov5s-v1.0",
                        "image_size": {"width": 640, "height": 480},
                        "timestamp": "2024-01-15T10:30:00Z",
                    },
                    "cached": False,
                },
                "message": "Анализ завершен",
            }
        }


class BatchAnalysisResponse(BaseModel):
    """Ответ на пакетный анализ."""

    task_ids: list[str] = Field(..., description="ID задач анализа")
    total_objects: int = Field(
        ..., description="Общее количество обнаруженных объектов"
    )
    processing_time_ms: float = Field(..., description="Общее время обработки (мс)")
