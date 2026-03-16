"""Эндпоинт для метрик мониторинга."""

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

from app.services.metrics import MetricsService

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Метрики Prometheus",
    description="Возвращает метрики в формате Prometheus",
)
async def get_metrics() -> PlainTextResponse:
    """
    Возвращает метрики сервиса в формате Prometheus.
    """
    metrics_data = MetricsService.get_metrics()
    return PlainTextResponse(content=metrics_data.decode("utf-8"))
