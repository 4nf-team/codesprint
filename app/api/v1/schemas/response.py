"""Схемы ответов для API v1."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    """Статус задачи анализа."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FaceResult(BaseModel):
    """
    Результат анализа одного лица.

    Attributes:
        face_index: Индекс лица в документе (начиная с 1)
        bbox: Координаты bounding box [x1, y1, x2, y2] в пикселях
        face_crop_b64: Base64-кодированное изображение лица в формате JPEG
        is_ai_generated: True если лицо сгенерировано нейросетью
        ai_confidence: Уверенность модели в диапазоне 0.0-1.0
        realness_score: Процент реалистичности в диапазоне 0-100
        is_unique: True если лицо уникально в документе
        similarity_details: Текстовое описание похожести с другими лицами
        argumentation: LLM-аргументация (доступна после запроса /api/argumentation)
    """

    face_index: int = Field(
        ...,
        description="Индекс лица в документе (начиная с 1)",
        ge=1,
        examples=[1, 2, 3],
    )
    bbox: list[float] = Field(
        ...,
        description="Координаты bounding box [x1, y1, x2, y2] в пикселях",
        min_length=4,
        max_length=4,
        examples=[[120.0, 45.0, 380.0, 420.0]],
    )
    face_crop_b64: str | None = Field(
        None, description="Base64-кодированное изображение лица в формате JPEG"
    )
    is_ai_generated: bool = Field(
        ..., description="True если лицо сгенерировано нейросетью"
    )
    ai_confidence: float = Field(
        ...,
        description="Уверенность модели в диапазоне 0.0-1.0",
        ge=0.0,
        le=1.0,
        examples=[0.9312],
    )
    realness_score: float = Field(
        ...,
        description="Процент реалистичности в диапазоне 0-100",
        ge=0.0,
        le=100.0,
        examples=[93.12],
    )
    is_unique: bool = Field(..., description="True если лицо уникально в документе")
    similarity_details: str = Field(
        ...,
        description="Текстовое описание похожести с другими лицами",
        examples=[
            "unique (no similar faces in session)",
            "similar to face #1 (cosine: 0.82)",
        ],
    )
    argumentation: str | None = Field(
        None, description="LLM-аргументация (доступна после запроса /api/argumentation)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "face_index": 1,
                "bbox": [120.0, 45.0, 380.0, 420.0],
                "face_crop_b64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
                "is_ai_generated": False,
                "ai_confidence": 0.9312,
                "realness_score": 93.12,
                "is_unique": True,
                "similarity_details": "unique (no similar faces in session)",
                "argumentation": None,
            }
        }
    )


class AnalysisResponse(BaseModel):
    """
    Ответ на запрос анализа документа.

    Attributes:
        filename: Имя загруженного файла
        total_images: Количество изображений в документе
        total_faces: Общее количество обнаруженных лиц
        faces: Список результатов анализа лиц
        summary: Текстовое резюме результатов анализа
    """

    filename: str = Field(
        ..., description="Имя загруженного файла", examples=["document.pdf"]
    )
    total_images: int = Field(
        ..., description="Количество изображений в документе", ge=0, examples=[2]
    )
    total_faces: int = Field(
        ..., description="Общее количество обнаруженных лиц", ge=0, examples=[3]
    )
    faces: list[FaceResult] = Field(
        default_factory=list, description="Список результатов анализа лиц"
    )
    summary: str = Field(
        ...,
        description="Текстовое резюме результатов анализа",
        examples=[
            "Found 2 image(s), 3 face(s). "
            "1 face(s) likely AI-generated. "
            "1 face(s) may not be unique."
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "filename": "document.pdf",
                "total_images": 2,
                "total_faces": 3,
                "faces": [
                    {
                        "face_index": 1,
                        "bbox": [120.0, 45.0, 380.0, 420.0],
                        "face_crop_b64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
                        "is_ai_generated": False,
                        "ai_confidence": 0.9312,
                        "realness_score": 93.12,
                        "is_unique": True,
                        "similarity_details": "unique (no similar faces in session)",
                        "argumentation": None,
                    },
                    {
                        "face_index": 2,
                        "bbox": [50.0, 100.0, 200.0, 300.0],
                        "face_crop_b64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
                        "is_ai_generated": True,
                        "ai_confidence": 0.8745,
                        "realness_score": 12.55,
                        "is_unique": False,
                        "similarity_details": "similar to face #1 (cosine: 0.82)",
                        "argumentation": None,
                    },
                ],
                "summary": (
                    "Found 2 image(s), 3 face(s). "
                    "1 face(s) likely AI-generated. "
                    "1 face(s) may not be unique."
                ),
            }
        }
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "result": {
                    "filename": "document.pdf",
                    "total_images": 2,
                    "total_faces": 3,
                    "faces": [],
                    "summary": "Found 2 image(s), 3 face(s).",
                },
                "message": "Анализ завершен",
            }
        }
    )
