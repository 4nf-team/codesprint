"""Схемы запросов для API v1."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class FileUploadRequest(BaseModel):
    """
    Схема для загрузки файла на анализ.

    Примечание: В FastAPI загрузка файлов через multipart/form-data
    обрабатывается напрямую через UploadFile. Эта схема используется
    для документации OpenAPI и валидации метаданных.

    Attributes:
        file: Файл для анализа (PDF, JPEG, PNG, WebP или BMP)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"description": "Загрузка PDF документа на анализ"}
        }
    )


# Тип для загружаемого файла в multipart/form-data
# Используется в эндпоинте как Annotated[UploadFile, File(...)]
FileType = Annotated[
    object, Field(description="Загружаемый файл (PDF, JPEG, PNG, WebP или BMP)")
]
