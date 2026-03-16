"""Middleware для логирования HTTP запросов."""

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования всех HTTP запросов.

    Логирует:
    - Метод и путь запроса
    - Заголовки
    - Тело запроса (опционально)
    - Время обработки
    - Статус ответа
    """

    def __init__(self, app, log_body: bool = False):
        """
        Инициализация middleware.

        Args:
            app: FastAPI приложение
            log_body: Логировать ли тело запроса
        """
        super().__init__(app)
        self.log_body = log_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Обработка запроса.

        Args:
            request: FastAPI request
            call_next: Следующий middleware/эндпоинт

        Returns:
            Response
        """
        start_time = time.time()

        # Получение тела запроса (если нужно)
        body = None
        if self.log_body and request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                # Восстанавливаем request для дальнейшей обработки
                await request.receive()
            except RuntimeError as e:
                logger.warning("Failed to read request body: %s", e)

        # Обработка запроса
        response = await call_next(request)

        # Вычисление времени обработки
        process_time = (time.time() - start_time) * 1000

        # Логирование
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time, 2),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
        }

        # Добавление тела запроса если нужно
        if body is not None:
            try:
                log_data["request_body"] = body.decode("utf-8")[
                    :1000
                ]  # Ограничиваем размер
            except UnicodeDecodeError:
                log_data["request_body"] = "<binary data>"

        # Логируем в JSON формате
        logger.info("HTTP Request", extra=log_data)

        # Добавляем заголовок с временем обработки
        response.headers["X-Process-Time"] = str(round(process_time / 1000, 3))

        return response
