"""ML утилиты и вспомогательные функции."""

from typing import Tuple, List, Dict, Any
import hashlib
import base64
from pathlib import Path


def compute_image_hash(image_bytes: bytes) -> str:
    """
    Вычисление SHA256 хэша изображения.

    Args:
        image_bytes: Байты изображения

    Returns:
        Хэш в шестнадцатеричном формате
    """
    return hashlib.sha256(image_bytes).hexdigest()


def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Кодирование изображения в base64.

    Args:
        image_bytes: Байты изображения

    Returns:
        base64 строка
    """
    return base64.b64encode(image_bytes).decode("utf-8")


def decode_base64_to_image(base64_string: str) -> bytes:
    """
    Декодирование base64 строки в байты изображения.

    Args:
        base64_string: base64 строка

    Returns:
        Байты изображения
    """
    return base64.b64decode(base64_string)


def scale_bounding_box(
    bbox: Dict[str, float], original_size: Tuple[int, int], target_size: Tuple[int, int]
) -> Dict[str, float]:
    """
    Масштабирование bounding box.

    Args:
        bbox: Исходный bounding box
        original_size: Исходный размер (ширина, высота)
        target_size: Целевой размер (ширина, высота)

    Returns:
        Масштабированный bounding box
    """
    orig_w, orig_h = original_size
    target_w, target_h = target_size

    scale_x = target_w / orig_w
    scale_y = target_h / orig_h

    return {
        "x": bbox["x"] * scale_x,
        "y": bbox["y"] * scale_y,
        "width": bbox["width"] * scale_x,
        "height": bbox["height"] * scale_y,
    }


def filter_detections(
    objects: List[Dict[str, Any]],
    confidence_threshold: float = 0.5,
    max_objects: int = 100,
) -> List[Dict[str, Any]]:
    """
    Фильтрация обнаруженных объектов.

    Args:
        objects: Список обнаруженных объектов
        confidence_threshold: Порог уверенности
        max_objects: Максимальное количество объектов

    Returns:
        Отфильтрованный список объектов
    """
    # Фильтрация по уверенности
    filtered = [obj for obj in objects if obj["confidence"] >= confidence_threshold]

    # Сортировка по уверенности (по убыванию)
    filtered.sort(key=lambda x: x["confidence"], reverse=True)

    # Ограничение количества
    return filtered[:max_objects]


def non_max_suppression(
    boxes: List[Dict[str, Any]], iou_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Non-maximum suppression для удаления дубликатов.

    Args:
        boxes: Список bounding box'ов
        iou_threshold: Порог IoU для подавления

    Returns:
        Отфильтрованный список
    """
    if not boxes:
        return []

    # Сортировка по уверенности
    boxes = sorted(boxes, key=lambda x: x["confidence"], reverse=True)

    kept = []

    for box in boxes:
        # Проверка пересечения с уже сохраненными
        keep = True
        for kept_box in kept:
            iou = calculate_iou(box["bbox"], kept_box["bbox"])
            if iou > iou_threshold:
                keep = False
                break

        if keep:
            kept.append(box)

    return kept


def calculate_iou(box1: Dict[str, float], box2: Dict[str, float]) -> float:
    """
    Вычисление Intersection over Union (IoU) двух bounding box'ов.

    Args:
        box1: Первый bounding box
        box2: Второй bounding box

    Returns:
        IoU значение
    """
    # Вычисление координат пересечения
    x1 = max(box1["x"], box2["x"])
    y1 = max(box1["y"], box2["y"])
    x2 = min(box1["x"] + box1["width"], box2["x"] + box2["width"])
    y2 = min(box1["y"] + box1["height"], box2["y"] + box2["height"])

    # Площадь пересечения
    intersection = max(0, x2 - x1) * max(0, y2 - y1)

    # Площади каждого box
    area1 = box1["width"] * box1["height"]
    area2 = box2["width"] * box2["height"]

    # IoU
    union = area1 + area2 - intersection

    if union == 0:
        return 0.0

    return intersection / union


def ensure_dir(path: str) -> Path:
    """
    Создание директории если она не существует.

    Args:
        path: Путь к директории

    Returns:
        Path объект
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
