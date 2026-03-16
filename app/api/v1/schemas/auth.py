"""Схемы для аутентификации и API-ключей."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateAPIKeyRequest(BaseModel):
    """Запрос создания API ключа."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, max_length=100)
    expires_days: int | None = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """Ответ с данными API ключа."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    api_key: str | None = None  # Только при создании, иначе None
    name: str | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
