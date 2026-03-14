"""Middleware для сбора метрик Prometheus."""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.metrics import MetricsService


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware для сбора метрик HTTP запросов в Prometheus.

    Автоматически записывает:
    - Количество запросов (по методу, эндпоинту, статусу)
    - Время обработки запроса
    - Ошибки
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Обработка запроса с сбором метрик.

        Args:
            request: FastAPI request
            call_next: Следующий middleware/эндпоинт

        Returns:
            Response
        """
        start_time = time.time()

        # Получаем путь запроса (без query параметров)
        endpoint = request.url.path

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Записываем метрики
            MetricsService.record_request(
                method=request.method, endpoint=endpoint, status=response.status_code
            )
            MetricsService.record_response_time(
                endpoint=endpoint, duration_seconds=duration
            )

            return response

        except Exception as exc:
            duration = time.time() - start_time

            # Записываем метрику ошибки
            error_type = type(exc).__name__
            MetricsService.record_error(error_type=error_type)

            # Записываем время обработки даже при ошибке
            MetricsService.record_response_time(
                endpoint=endpoint, duration_seconds=duration
            )

            raise
