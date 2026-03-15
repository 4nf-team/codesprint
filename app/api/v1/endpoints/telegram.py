"""Telegram WebApp аутентификация."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.deps import get_auth_service
from app.core.config import settings
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    """Запрос аутентификации через Telegram."""

    init_data: str = Field(..., description="Строка query параметров от Telegram")


class TelegramAuthResponse(BaseModel):
    """Ответ при успешной аутентификации через Telegram."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
    api_key: str | None = Field(None, description="API ключ для использования")


class TokenResponse(BaseModel):
    """Ответ с JWT токенами."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Верификация данных от Telegram WebApp.

    Алгоритм проверки:
    1. Разделить init_data на пары ключ-значение
    2. Извлечь hash (если есть)
    3. Отсортировать оставшиеся пары по алфавиту ключей
    4. Собрать строку в формате "key1=value1\nkey2=value2..."
    5. Вычислить HMAC-SHA256 от этой строки с bot_token как ключом
    6. Сравнить с hash (используя hmac.compare_digest)

    Args:
        init_data: Строка query параметров от Telegram
        bot_token: Токен бота от @BotFather

    Returns:
        dict с данными пользователя если валидно

    Raises:
        ValueError: Если подпись неверна, данные просрочены или некорректны
    """
    if not init_data:
        raise ValueError("Empty init_data")

    # Парсим query string
    pairs = {}
    hash_value = None

    for pair in init_data.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            if key == "hash":
                hash_value = value
            else:
                pairs[key] = value

    if not hash_value:
        raise ValueError("Missing hash in init_data")

    # Проверяем auth_date (защита от replay-атак)
    if "auth_date" in pairs:
        try:
            auth_date = int(pairs["auth_date"])
            # Проверяем, что данные не старше 24 часов
            current_time = int(datetime.now(timezone.utc).timestamp())
            if current_time - auth_date > 24 * 3600:
                raise ValueError("init_data is too old")
        except (ValueError, TypeError):
            raise ValueError("Invalid auth_date")
    else:
        logger.warning("auth_date not found in init_data")

    # Собираем строку для проверки подписи
    # Ключи сортируем по алфавиту
    sorted_keys = sorted(pairs.keys())
    data_check_string = "\n".join([f"{key}={pairs[key]}" for key in sorted_keys])

    # Вычисляем HMAC-SHA256
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hmac_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # Сравниваем подписи с защитой от timing-атак
    if not hmac.compare_digest(hmac_hash, hash_value):
        logger.warning(
            "Invalid Telegram signature. Expected: %s, Got: %s", hash_value, hmac_hash
        )
        raise ValueError("Invalid signature")

    # Извлекаем и парсим user данные
    if "user" not in pairs:
        raise ValueError("Missing user data")

    try:
        user_data = json.loads(pairs["user"])
    except json.JSONDecodeError as e:
        logger.exception("Failed to parse user JSON")
        raise ValueError("Invalid user data") from e

    # Проверяем обязательные поля
    if "id" not in user_data:
        raise ValueError("User ID is required")

    logger.info(
        "Telegram authentication successful for user_id=%d, username=%s",
        user_data.get("id"),
        user_data.get("username"),
    )

    return user_data


@router.post("/telegram", response_model=TelegramAuthResponse)
async def telegram_auth(
    request: TelegramAuthRequest, auth_service: AuthService = Depends(get_auth_service)
):
    """
    Аутентификация через Telegram WebApp.

    Процесс:
    1. Получает init_data от клиента
    2. Верифицирует подпись через HMAC-SHA256
    3. Проверяет, что auth_date не старше 24 часов
    4. Находит или создает пользователя по telegram_id
    5. Создает JWT токены
    6. Создает API-ключ для использования
    7. Возвращает токены и API-ключ

    Returns:
        TelegramAuthResponse с токенами и данными пользователя

    Raises:
        HTTPException 401: Неверная подпись или просроченные данные
        HTTPException 500: Ошибка сервера
    """
    try:
        # Проверка настройки Telegram бота
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning(
                "Telegram authentication attempted but bot token not configured"
            )
            raise HTTPException(
                status_code=503, detail="Telegram authentication is not configured"
            )

        # Верификация данных от Telegram
        user_data = verify_telegram_init_data(
            request.init_data, settings.TELEGRAM_BOT_TOKEN
        )

        telegram_id = user_data["id"]
        username = user_data.get("username")
        first_name = user_data.get("first_name")
        last_name = user_data.get("last_name")

        # Поиск или создание пользователя
        user = await auth_service.get_user_by_telegram_id(telegram_id)
        if not user:
            user = await auth_service.create_user(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )

        # Создание JWT токенов
        access_token, refresh_token = await auth_service.create_session(user.id)

        # Создание API-ключа для этого сеанса
        api_key = await auth_service.create_api_key(
            user_id=user.id,
            name=f"Telegram WebApp {datetime.now(timezone.utc).isoformat()}",
        )

        return TelegramAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_premium": user.is_premium,
            },
            api_key=api_key,
        )

    except ValueError as e:
        logger.warning("Telegram auth failed: %s", str(e))
        raise HTTPException(
            status_code=401, detail="Invalid Telegram authentication"
        ) from e
    except Exception as e:
        logger.exception("Telegram auth failed with unexpected error")
        raise HTTPException(status_code=500, detail="Authentication failed") from e


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str, auth_service: AuthService = Depends(get_auth_service)
):
    """
    Обновление access токена по refresh токену.

    Args:
        refresh_token: Refresh токен

    Returns:
        TokenResponse с новыми токенами

    Raises:
        HTTPException 401: Неверный refresh токен
        HTTPException 500: Ошибка сервера
    """
    try:
        tokens = await auth_service.refresh_session(refresh_token)
        if not tokens:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return TokenResponse(access_token=tokens[0], refresh_token=tokens[1])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Token refresh failed")
        raise HTTPException(status_code=500, detail="Token refresh failed") from e
