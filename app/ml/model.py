"""ML Model Service - Placeholder implementation."""

from typing import Dict, Any, List
import random
import time
import io

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MLModel:
    """
    Класс для работы с ML моделью детекции объектов (заглушка).

    Эта реализация возвращает фиктивные предсказания для разработки
    и тестирования без реальной ML модели.

    Attributes:
        model: Загруженная модель (None для заглушки)
        device: Устройство для инференса (cpu)
        version: Версия модели
    """

    def __init__(self) -> None:
        self.model = None
        self.device = "cpu"
        self.version = "placeholder-v1.0"
        self.class_names = [
            "person",
            "bicycle",
            "car",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "couch",
            "potted plant",
            "bed",
            "dining table",
            "toilet",
            "tv",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush",
        ]

    async def load(self) -> None:
        """
        Загрузка модели (заглушка).

        Логирует информацию о загрузке, но не загружает реальную модель.
        """
        logger.info(
            f"ML Model placeholder initialized. "
            f"Model path: {settings.MODEL_PATH}, "
            f"Device: {self.device}, "
            f"Version: {self.version}"
        )
        self.model = "placeholder"

    async def predict(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Выполнение предсказания на изображении (заглушка).

        Args:
            image_bytes: Байты изображения

        Returns:
            Результат предсказания с обнаруженными объектами (фиктивными)
        """
        if self.model is None:
            await self.load()

        start_time = time.time()

        # Получаем размер изображения из байтов
        image_width, image_height = self._get_image_size(image_bytes)

        # Генерируем фиктивные предсказания
        objects = self._generate_dummy_predictions(image_width, image_height)

        processing_time = (time.time() - start_time) * 1000

        logger.debug(
            f"Prediction completed (placeholder): {len(objects)} objects, "
            f"{processing_time:.2f}ms"
        )

        return {
            "objects": objects,
            "image_size": {
                "width": image_width,
                "height": image_height,
            },
            "processing_time_ms": processing_time,
            "model_version": self.version,
        }

    def _get_image_size(self, image_bytes: bytes) -> tuple:
        """
        Получение размера изображения из байтов.

        Args:
            image_bytes: Байты изображения

        Returns:
            Кортеж (ширина, высота)
        """
        try:
            # Пробуем использовать PIL для получения размера
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
            return image.size  # (width, height)
        except Exception:
            # Если не удалось, возвращаем размеры по умолчанию
            return (640, 480)

    def _generate_dummy_predictions(
        self, image_width: int, image_height: int
    ) -> List[Dict[str, Any]]:
        """
        Генерация фиктивных предсказаний.

        Args:
            image_width: Ширина изображения
            image_height: Высота изображения

        Returns:
            Список обнаруженных объектов
        """
        objects = []

        # Генерируем 0-3 объекта случайным образом
        num_objects = random.randint(0, 3)

        for _ in range(num_objects):
            # Случайный класс
            label = random.choice(self.class_names)

            # Случайная уверенность
            confidence = round(random.uniform(0.5, 0.98), 2)

            # Случайный bounding box
            x = random.randint(0, max(0, image_width - 100))
            y = random.randint(0, max(0, image_height - 100))
            width = random.randint(50, min(200, image_width - x))
            height = random.randint(50, min(200, image_height - y))

            objects.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "bbox": {
                        "x": float(x),
                        "y": float(y),
                        "width": float(width),
                        "height": float(height),
                    },
                }
            )

        return objects


# Глобальный экземпляр модели
ml_model = MLModel()
