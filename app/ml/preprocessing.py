"""Предобработка изображений для ML модели."""

from typing import Tuple, Optional
import io
from PIL import Image
import torch
from torchvision import transforms


class ImagePreprocessor:
    """
    Класс для предобработки изображений.

    Attributes:
        target_size: Целевой размер изображения (ширина, высота)
        normalize_mean: Средние значения для нормализации
        normalize_std: Стандартные отклонения для нормализации
    """

    def __init__(
        self,
        target_size: Tuple[int, int] = (640, 640),
        normalize_mean: Tuple[float, float, float] = (0.485, 0.456, 0.406),
        normalize_std: Tuple[float, float, float] = (0.229, 0.224, 0.225),
    ):
        self.target_size = target_size
        self.normalize_mean = normalize_mean
        self.normalize_std = normalize_std

        self.transform = transforms.Compose(
            [
                transforms.Resize(target_size),
                transforms.ToTensor(),
                transforms.Normalize(mean=normalize_mean, std=normalize_std),
            ]
        )

    def preprocess_bytes(self, image_bytes: bytes) -> torch.Tensor:
        """
        Предобработка изображения из байтов.

        Args:
            image_bytes: Байты изображения

        Returns:
            Предобработанный тензор
        """
        image = Image.open(io.BytesIO(image_bytes))

        # Конвертация в RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Применение трансформаций
        tensor = self.transform(image)

        # Добавление batch dimension
        tensor = tensor.unsqueeze(0)

        return tensor

    def preprocess_pil(self, image: Image.Image) -> torch.Tensor:
        """
        Предобработка PIL изображения.

        Args:
            image: PIL изображение

        Returns:
            Предобработанный тензор
        """
        # Конвертация в RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Применение трансформаций
        tensor = self.transform(image)

        # Добавление batch dimension
        tensor = tensor.unsqueeze(0)

        return tensor

    def get_original_size(self, image_bytes: bytes) -> Tuple[int, int]:
        """
        Получение исходного размера изображения.

        Args:
            image_bytes: Байты изображения

        Returns:
            (ширина, высота)
        """
        image = Image.open(io.BytesIO(image_bytes))
        return image.size

    @staticmethod
    def validate_image(
        image_bytes: bytes,
        max_size: int = 50 * 1024 * 1024,  # 50MB
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидация изображения.

        Args:
            image_bytes: Байты изображения
            max_size: Максимальный размер в байтах

        Returns:
            (валидно, сообщение об ошибке)
        """
        # Проверка размера
        if len(image_bytes) > max_size:
            return False, f"Image too large: {len(image_bytes)} bytes (max {max_size})"

        # Проверка что это валидное изображение
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image.verify()
            return True, None
        except Exception as e:
            return False, f"Invalid image: {str(e)}"
