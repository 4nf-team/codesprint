"""
Эндпоинт для анализа документов с лицами.

Позволяет загружать документы (PDF или изображения) и анализировать их
на наличие лиц с определением AI-сгенерированных лиц.

## Поддерживаемые форматы файлов:
- PDF (.pdf)
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- BMP (.bmp)

## Коды ответа:
- 200: Успешный анализ документа
- 400: Некорректный запрос (пустой файл, неподдерживаемый формат)
- 401: Не авторизован
- 413: Размер файла превышает максимальный
- 422: PDF не содержит изображений для анализа
- 429: Превышен лимит запросов
- 500: Внутренняя ошибка сервера
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.v1.deps import RateLimitService, get_current_user
from app.api.v1.schemas.error import ErrorResponse
from app.api.v1.schemas.response import TaskStatus, TaskStatusResponse
from app.workers.tasks import analyze_image_task

logger = logging.getLogger(__name__)

router = APIRouter()

# Поддерживаемые форматы файлов
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
}

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# Максимальный размер файла (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Минимальный размер PDF для проверки на наличие изображений
MIN_PDF_SIZE = 100


@router.post(
    "/analyze",
    response_model=TaskStatusResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Некорректный запрос"},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        413: {"model": ErrorResponse, "description": "Размер файла превышает 10MB"},
        422: {"model": ErrorResponse, "description": "PDF не содержит изображений"},
        429: {"model": ErrorResponse, "description": "Превышен лимит запросов"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
    },
    summary="Анализ документа",
    description="Загружает и анализирует документ (PDF или изображение) на наличие лиц",
)
async def analyze_document(
    _request: Request,
    file: UploadFile = File(
        ..., description="Документ для анализа (PDF, JPEG, PNG, WebP или BMP)"
    ),
    user: dict = Depends(get_current_user),
    rate_limit: RateLimitService = Depends(),
) -> TaskStatusResponse:
    """
    Анализ загруженного документа.

    Принимает на вход PDF-документ или изображение и возвращает результаты
    анализа лиц с определением AI-сгенерированных лиц.

    ## Пример запроса (curl):
    ```bash
    curl -X POST "http://localhost:8000/api/v1/analyze" \\
        -H "Authorization: Bearer <token>" \\
        -F "file=@document.pdf"
    ```

    ## Пример успешного ответа (200):
    ```json
    {
        "filename": "document.pdf",
        "total_images": 2,
        "total_faces": 3,
        "faces": [
            {
                "face_index": 1,
                "bbox": [120.0, 45.0, 380.0, 420.0],
                "face_crop_b64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
                "is_ai_generated": false,
                "ai_confidence": 0.9312,
                "realness_score": 93.12,
                "is_unique": true,
                "similarity_details": "unique (no similar faces in session)",
                "argumentation": null
            }
        ],
        "summary": (
            "Found 2 image(s), 3 face(s). 1 face(s) likely AI-generated. "
            "1 face(s) may not be unique."
        )
    }
    ```

    ## Примеры ошибок:

    - **400** - Пустой файл:
      ```json
      {"error": "Файл пустой", "detail": "Загруженный файл не содержит данных"}
      ```

    - **400** - Неподдерживаемый формат:
      ```json
      {
          "error": "Неподдерживаемый формат файла",
          "detail": "Поддерживаются: PDF, JPEG, PNG, WebP, BMP",
      }
      ```

    - **422** - PDF без изображений:
      ```json
      {
          "error": "PDF не содержит изображений",
          "detail": "В документе не найдено изображений для анализа",
      }
      ```

    ## Параметры:
    - **file**: Файл для анализа (обязательно)
        - Тип: multipart/form-data
        - Максимальный размер: 10MB
        - Форматы: PDF, JPEG, PNG, WebP, BMP
    """
    # Проверка rate limit
    await rate_limit.check()

    filename = file.filename or "unknown"

    logger.info("Начало анализа файла: %s, тип: %s", filename, file.content_type)

    # Проверка на пустой файл (Content-Length может быть 0)
    # Читаем файл для проверки
    try:
        file_content = await file.read()
    except OSError:
        logger.exception("Ошибка при чтении файла")
        raise HTTPException(status_code=400, detail="Не удалось прочитать файл")

    # Проверка на пустой файл
    if len(file_content) == 0:
        logger.warning("Пустой файл: %s", filename)
        raise HTTPException(status_code=400, detail="Файл пустой")

    # Проверка размера файла
    if len(file_content) > MAX_FILE_SIZE:
        logger.warning(
            "Файл слишком большой: %s, размер: %s",
            filename,
            len(file_content),
        )
        raise HTTPException(status_code=413, detail="Размер файла превышает 10MB")

    # Проверка формата файла по MIME-типу
    content_type = file.content_type or ""
    if content_type not in SUPPORTED_MIME_TYPES:
        # Проверяем по расширению файла
        file_ext = ""
        if "." in filename:
            file_ext = "." + filename.rsplit(".", 1)[1].lower()

        if file_ext not in SUPPORTED_EXTENSIONS:
            logger.warning(
                "Неподдерживаемый формат: %s, тип: %s",
                filename,
                content_type,
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Неподдерживаемый формат файла. "
                    "Поддерживаются: PDF, JPEG, PNG, WebP, BMP"
                ),
            )

    # Проверка PDF на наличие изображений
    is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")

    if is_pdf:
        # Заглушка: проверка PDF на наличие изображений
        # TODO: Реальная проверка будет добавлена с ML моделью
        # Пока возвращаем тестовые данные для верификации формата
        has_images = len(file_content) > MIN_PDF_SIZE
        if not has_images:
            logger.warning("PDF не содержит изображений: %s", filename)
            raise HTTPException(status_code=422, detail="PDF не содержит изображений")

    # Вызов Celery задачи для асинхронного анализа изображений
    user_id = user.get("user_id")

    try:
        task = analyze_image_task.delay(
            image_bytes=file_content,
            filename=filename,
            user_id=user_id,
            content_type=content_type,
        )

        logger.info(
            "Задача анализа поставлена в очередь: %s, файл: %s",
            task.id,
            filename,
        )

        return TaskStatusResponse(
            task_id=task.id,
            status=TaskStatus.PENDING,
            message="Задача анализа поставлена в очередь",
        )
    except RuntimeError:
        logger.exception("Ошибка при создании задачи анализа")
        raise HTTPException(
            status_code=500, detail="Не удалось поставить задачу в очередь"
        )
