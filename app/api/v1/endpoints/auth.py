"""Эндпоинты для управления API-ключами."""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.deps import get_auth_service, get_current_user
from app.api.v1.schemas.auth import APIKeyResponse, CreateAPIKeyRequest
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[APIKeyResponse]:
    """
    Получить список API-ключей пользователя.

    Returns:
        Список API-ключей без полного ключа (только метаданные)
    """
    try:
        user_id = current_user["user_id"]
        api_keys = await auth_service.get_user_api_keys(user_id=user_id)

        # Преобразуем в APIKeyResponse без api_key (None)
        result = []
        for key in api_keys:
            result.append(
                APIKeyResponse(
                    id=key.id,
                    api_key=None,  # Не возвращаем полный ключ в списке
                    name=key.name,
                    is_active=key.is_active,
                    expires_at=key.expires_at,
                    created_at=key.created_at,
                )
            )

        logger.info(
            "Пользователь %d запросил список API-ключей: %d найдено",
            user_id,
            len(result),
        )
        return result

    except SQLAlchemyError:
        logger.exception("Ошибка БД при получении списка API-ключей")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> APIKeyResponse:
    """
    Создать новый API-ключ.

    Returns:
        API-ключ с полным значением ключа (возвращается только один раз)
    """
    try:
        user_id = current_user["user_id"]
        api_key = await auth_service.create_api_key(
            user_id=user_id, name=request.name, expires_days=request.expires_days
        )

        # Получаем созданный ключ из БД для получения метаданных
        user_keys = await auth_service.get_user_api_keys(user_id=user_id)
        new_key = user_keys[0] if user_keys else None

        if not new_key:
            raise HTTPException(
                status_code=500, detail="Не удалось получить созданный ключ"
            )

        logger.info("Пользователь %d создал новый API-ключ: id=%d", user_id, new_key.id)

        return APIKeyResponse(
            id=new_key.id,
            api_key=api_key,  # Возвращаем полный ключ только при создании
            name=new_key.name,
            is_active=new_key.is_active,
            expires_at=new_key.expires_at,
            created_at=new_key.created_at,
        )

    except ValueError as e:
        logger.warning("Ошибка при создании API-ключа: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except SQLAlchemyError:
        logger.exception("Ошибка БД при создании API-ключа")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(
    key_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """
    Ротировать существующий API-ключ.

    Args:
        key_id: ID API-ключа для ротации

    Returns:
        Новый API-ключ и сообщение об успехе
    """
    try:
        user_id = current_user["user_id"]

        # Получаем ключ для проверки принадлежности
        user_keys = await auth_service.get_user_api_keys(user_id=user_id)
        key_exists = any(k.id == key_id for k in user_keys)

        if not key_exists:
            logger.warning(
                "Попытка ротации чужого или несуществующего ключа: key_id=%d, user_id=%d",
                key_id,
                user_id,
            )
            raise HTTPException(
                status_code=403, detail="Ключ не найден или не принадлежит вам"
            )

        new_key = await auth_service.rotate_api_key(key_id=key_id)

        if not new_key:
            logger.warning("Не удалось ротировать ключ: key_id=%d", key_id)
            raise HTTPException(status_code=404, detail="Ключ не найден или неактивен")

        logger.info("Пользователь %d ротировал API-ключ: key_id=%d", user_id, key_id)

        return {"api_key": new_key, "message": "Key rotated successfully"}

    except SQLAlchemyError:
        logger.exception("Ошибка БД при ротации API-ключа")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, bool]:
    """
    Деактивировать API-ключ.

    Args:
        key_id: ID API-ключа для деактивации

    Returns:
        Статус успеха и сообщение
    """
    try:
        user_id = current_user["user_id"]

        # Получаем ключ для проверки принадлежности
        user_keys = await auth_service.get_user_api_keys(user_id=user_id)
        key_exists = any(k.id == key_id for k in user_keys)

        if not key_exists:
            logger.warning(
                "Попытка удаления чужого или несуществующего ключа: key_id=%d, user_id=%d",
                key_id,
                user_id,
            )
            raise HTTPException(
                status_code=403, detail="Ключ не найден или не принадлежит вам"
            )

        success = await auth_service.deactivate_api_key(key_id=key_id)

        if not success:
            logger.warning("Не удалось деактивировать ключ: key_id=%d", key_id)
            raise HTTPException(status_code=404, detail="Ключ не найден")

        logger.info(
            "Пользователь %d деактивировал API-ключ: key_id=%d", user_id, key_id
        )

        return {"success": True, "message": "Key deactivated"}

    except SQLAlchemyError:
        logger.exception("Ошибка БД при деактивации API-ключа")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
