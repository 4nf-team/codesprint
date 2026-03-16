"""Сервис анализа изображений.

Содержит функции для анализа изображений и обнаружения лиц.
В настоящее время возвращает тестовые данные для верификации API.
"""

from app.api.v1.schemas.response import AnalysisResponse, FaceResult


def analyze_image(_file_content: bytes, filename: str) -> AnalysisResponse:
    """
    Анализирует изображение и возвращает результаты обнаружения лиц.

    ВНИМАНИЕ: Это заглушка. ML модель ещё не интегрирована.
    Функция возвращает тестовые данные для верификации API контракта.

    Args:
        file_content: Содержимое файла в виде байтов
        filename: Имя файла изображения

    Returns:
        AnalysisResponse: Результат анализа с данными о лицах
    """
    # Заглушка: тестовые данные для верификации API
    test_faces = [
        FaceResult(
            face_index=1,
            bbox=[120.0, 45.0, 380.0, 420.0],
            face_crop_b64=None,
            is_ai_generated=False,
            ai_confidence=0.9312,
            realness_score=93.12,
            is_unique=True,
            similarity_details="unique (no similar faces in session)",
            argumentation=None,
        ),
    ]

    total_faces = len(test_faces)
    total_images = 1

    summary = (
        f"Found {total_images} image(s), {total_faces} face(s). "
        f"0 face(s) likely AI-generated. 0 face(s) may not be unique."
    )

    return AnalysisResponse(
        filename=filename,
        total_images=total_images,
        total_faces=total_faces,
        faces=test_faces,
        summary=summary,
    )
