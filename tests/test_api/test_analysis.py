"""Тесты эндпоинта анализа изображений."""

from fastapi import status


class TestAnalysisEndpoint:
    """Тесты эндпоинта анализа."""

    def test_analyze_without_auth(self, client, sample_image_bytes):
        """Тест анализа без API ключа."""
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", sample_image_bytes, "image/jpeg")},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_analyze_with_invalid_file_type(self, client, test_api_key):
        """Тест анализа с невалидным типом файла."""
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.txt", b"not an image", "text/plain")},
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_analyze_success(self, client, sample_image_bytes, test_api_key):
        """Тест успешного анализа (возвращает task_id)."""
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", sample_image_bytes, "image/jpeg")},
            headers={"X-API-Key": test_api_key},
        )
        # Должен вернуть 202 Accepted (задача поставлена в очередь)
        assert response.status_code == status.HTTP_202_ACCEPTED

        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert data["status"] in ["pending", "processing"]

    def test_get_task_status_not_found(self, client, test_api_key):
        """Тест получения статуса несуществующей задачи."""
        response = client.get(
            "/api/v1/tasks/nonexistent-task-id", headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_result_not_found(self, client, test_api_key):
        """Тест получения несуществующего результата."""
        response = client.get(
            "/api/v1/result/nonexistent-task-id", headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
