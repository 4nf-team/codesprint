"""Эндпоинт для анализа изображений."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import RateLimitService, get_current_user
from app.api.v1.schemas.error import ErrorResponse
from app.api.v1.schemas.response import AnalysisResponse, TaskStatusResponse
from app.models.database import get_db
from app.services.database import DatabaseService
from app.workers.celery_app import celery_app
from app.workers.tasks import analyze_image_task

router = APIRouter()


@router.post(
    "/analyze",
    response_model=TaskStatusResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Анализ изображения",
    description="Загружает и анализирует изображение с помощью ML модели",
)
async def analyze_image(
    request: Request,
    file: UploadFile = File(..., description="Изображение для анализа"),
    user: dict = Depends(get_current_user),
    rate_limit: RateLimitService = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Анализ загруженного изображения.

    - **file**: Изображение в формате JPEG/PNG

    Возвращает ID задачи для отслеживания статуса.
    """
    # Проверка rate limit
    await rate_limit.check()

    # Валидация типа файла
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")

    try:
        # Чтение файла
        image_bytes = await file.read()

        # Проверка размера файла (макс 10MB)
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Размер файла превышает 10MB")

        # Создаем задачу в БД
        db_service = DatabaseService(db)
        import hashlib

        image_hash = hashlib.sha256(image_bytes).hexdigest()
        task_id = await db_service.create_analysis_task(
            user_id=user.get("user_id", "anonymous"), image_hash=image_hash
        )

        # Отправляем задачу в Celery
        celery_task = analyze_image_task.delay(
            image_bytes=image_bytes,
            filename=file.filename or "unknown.jpg",
            user_id=user.get("user_id", "anonymous"),
            content_type=file.content_type,
        )

        return TaskStatusResponse(
            task_id=celery_task.id,
            status="pending",
            message="Задача поставлена в очередь",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при анализе изображения: {str(e)}"
        )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Получить статус задачи",
    description="Получает статус асинхронной задачи по ID",
)
async def get_task_status(
    task_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение статуса задачи по ID.

    - **task_id**: ID задачи анализа

    Возвращает статус задачи и результат (если завершена).
    """
    # Проверяем статус в Celery
    try:
        celery_task = celery_app.AsyncResult(task_id)
        celery_status = celery_task.state

        # Маппинг статуса Celery на наш статус
        status_map = {
            "PENDING": "pending",
            "STARTED": "processing",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "RETRY": "processing",
        }
        status = status_map.get(celery_status, "pending")

        result = None
        message = None

        if celery_status == "SUCCESS":
            result = celery_task.result
            message = "Анализ завершен"
        elif celery_status == "FAILURE":
            message = f"Ошибка: {celery_task.info}"
        elif celery_status == "PENDING":
            message = "Задача ожидает обработки"
        else:
            message = f"Статус: {celery_status}"

        return TaskStatusResponse(
            task_id=task_id, status=status, result=result, message=message
        )
    except Exception as e:
        # Если не найден в Celery, проверяем БД
        db_service = DatabaseService(db)
        db_result = await db_service.get_analysis_result(task_id)

        if db_result:
            return TaskStatusResponse(
                task_id=task_id,
                status="completed",
                result=db_result.get("result"),
                message="Анализ завершен",
            )

        raise HTTPException(status_code=404, detail="Задача не найдена")


@router.get(
    "/result/{task_id}",
    response_model=AnalysisResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Получить результат анализа",
    description="Получает результат асинхронного анализа по ID задачи",
)
async def get_analysis_result(
    task_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение результата анализа по ID задачи.

    - **task_id**: ID задачи анализа

    Возвращает результаты если анализ завершен.
    """
    db_service = DatabaseService(db)
    result = await db_service.get_analysis_result(task_id)

    if not result:
        raise HTTPException(
            status_code=404, detail="Задача не найдена или еще не завершена"
        )

    return AnalysisResponse(**result)
