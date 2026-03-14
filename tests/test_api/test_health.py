"""Тесты health check эндпоинта."""

from fastapi import status


class TestHealthEndpoint:
    """Тесты health check."""

    def test_health_check_success(self, client):
        """Тест успешного health check."""
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data

    def test_health_check_structure(self, client):
        """Тест структуры ответа health check."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "services" in data
        services = data["services"]
        assert "database" in services
        assert "cache" in services
        assert "model" in services
        assert "queue" in services

    def test_liveness_check(self, client):
        """Тест liveness probe."""
        response = client.get("/api/v1/health/live")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("alive") is True

    def test_readiness_check(self, client):
        """Тест readiness probe."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "ready" in data
