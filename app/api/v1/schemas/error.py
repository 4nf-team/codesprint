"""Схемы ошибок для API v1."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """
    Стандартизированный ответ об ошибке.

    Attributes:
        error: Тип ошибки
        message: Человекочитаемое сообщение
        details: Дополнительные детали ошибки (опционально)
        request_id: ID запроса для трассировки
        timestamp: Время возникновения ошибки
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "validation_error",
                "message": "Неверные данные в запросе",
                "details": {"field": "image", "issue": "file too large"},
                "request_id": "req_123456789",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    )

    error: str = Field(..., description="Тип ошибки")
    message: str = Field(..., description="Сообщение об ошибке")
    details: dict[str, Any] | None = Field(None, description="Дополнительные детали")
    request_id: str | None = Field(None, description="ID запроса")
    timestamp: str = Field(..., description="Время ошибки в ISO формате")


class ValidationErrorDetail(BaseModel):
    """Детали валидационного error."""

    field: str = Field(..., description="Поле с ошибкой")
    issue: str = Field(..., description="Описание проблемы")
    received_value: Any = Field(..., description="Полученное значение")
