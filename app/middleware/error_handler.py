"""Middleware для глобальной обработки ошибок."""

import traceback
import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.schemas.error import ErrorResponse
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware для глобальной обработки исключений.

    Перехватывает все исключения и возвращает стандартизированные JSON ответы.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Обработка запроса с обработкой ошибок.

        Args:
            request: FastAPI request
            call_next: Следующий middleware/эндпоинт

        Returns:
            Response (обычный или error response)
        """
        try:
            return await call_next(request)

        except HTTPException as exc:
            # FastAPI HTTPException - возвращаем как есть
            logger.warning(
                f"HTTPException: {exc.status_code} - {exc.detail}",
                extra={"path": request.url.path, "status_code": exc.status_code},
            )

            return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(
                    error="http_error",
                    message=exc.detail,
                    details=None,
                    request_id=None,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ).dict(),
            )

        except Exception as exc:
            # Неожиданные исключения
            error_id = str(uuid.uuid4())[:8]

            logger.exception(
                f"Unhandled exception (ID: {error_id}): {exc}",
                exc_info=True,
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "error_id": error_id,
                },
            )

            # В development режиме возвращаем stack trace
            details = None
            if settings.DEBUG:
                details = {
                    "error_id": error_id,
                    "traceback": traceback.format_exc(),
                    "type": type(exc).__name__,
                }

            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    error="internal_server_error",
                    message="Внутренняя ошибка сервера",
                    details=details,
                    request_id=error_id,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ).dict(),
            )
