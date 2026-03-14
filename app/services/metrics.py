"""Сервис сбора метрик на основе Prometheus client."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from typing import Dict, Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Определяем метрики
REQUESTS_TOTAL = Counter(
    "image_analysis_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "image_analysis_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint"],
)

ANALYSIS_TOTAL = Counter(
    "image_analysis_operations_total", "Total number of analysis operations"
)

CACHE_HITS = Counter("image_analysis_cache_hits_total", "Total number of cache hits")

CACHE_MISSES = Counter(
    "image_analysis_cache_misses_total", "Total number of cache misses"
)

ERRORS_TOTAL = Counter(
    "image_analysis_errors_total", "Total number of errors", ["error_type"]
)

ACTIVE_TASKS = Gauge(
    "image_analysis_active_tasks", "Number of currently processing tasks"
)

QUEUE_SIZE = Gauge(
    "image_analysis_queue_size", "Number of tasks in queue", ["queue_name"]
)

MODEL_INFERENCE_TIME = Histogram(
    "image_analysis_model_inference_seconds", "Model inference time in seconds"
)


class MetricsService:
    """
    Сервис сбора метрик для мониторинга.
    Предоставляет интерфейс для работы с Prometheus метриками.
    """

    @staticmethod
    def record_request(method: str, endpoint: str, status: int):
        """Запись успешного запроса."""
        REQUESTS_TOTAL.labels(
            method=method, endpoint=endpoint, status=str(status)
        ).inc()

    @staticmethod
    def record_error(error_type: str):
        """Запись ошибки."""
        ERRORS_TOTAL.labels(error_type=error_type).inc()

    @staticmethod
    def record_response_time(endpoint: str, duration_seconds: float):
        """
        Запись времени ответа.

        Args:
            endpoint: Эндпоинт
            duration_seconds: Время ответа в секундах
        """
        REQUEST_DURATION.labels(endpoint=endpoint).observe(duration_seconds)

    @staticmethod
    def record_analysis():
        """Запись выполненного анализа."""
        ANALYSIS_TOTAL.inc()

    @staticmethod
    def record_cache_hit():
        """Запись попадания в кэш."""
        CACHE_HITS.inc()

    @staticmethod
    def record_cache_miss():
        """Запись промаха кэша."""
        CACHE_MISSES.inc()

    @staticmethod
    def set_active_tasks(count: int):
        """Установка количества активных задач."""
        ACTIVE_TASKS.set(count)

    @staticmethod
    def set_queue_size(queue_name: str, size: int):
        """Установка размера очереди."""
        QUEUE_SIZE.labels(queue_name=queue_name).set(size)

    @staticmethod
    def record_model_inference_time(duration_seconds: float):
        """Запись времени инференса модели."""
        MODEL_INFERENCE_TIME.observe(duration_seconds)

    @staticmethod
    def get_metrics() -> bytes:
        """
        Получение метрик в формате Prometheus.

        Returns:
            Метрики в байтах в формате Prometheus
        """
        return generate_latest(REGISTRY)

    @staticmethod
    def reset():
        """Сброс всех метрик (для тестов)."""
        # Prometheus client не поддерживает сброс через стандартный API
        # Для тестов нужно пересозвать метрики или использовать custom registry
        pass
