"""Сервис аутентификации и авторизации."""

import secrets
from datetime import UTC, datetime, timedelta

import argon2
from argon2 import PasswordHasher
from jose import JWTError, jwt
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.database import (
    APIKeyRotationPolicy,
    AsyncSessionLocal,
    TelegramSession,
    User,
    UserAPIKey,
)

logger = get_logger(__name__)

# Инициализация хэшера argon2
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


# ========== Функции хэширования API-ключей ==========


def hash_api_key(api_key: str) -> str:
    """
    Хэширует API ключ с использованием argon2.

    Args:
        api_key: Открытый API ключ

    Returns:
        Хэшированный ключ
    """
    return ph.hash(api_key)


def verify_api_key(api_key: str, hash_value: str) -> bool:
    """
    Проверяет API ключ против хэша.

    Args:
        api_key: API ключ для проверки
        hash_value: Хэшированный ключ из БД

    Returns:
        True если ключ валиден, иначе False
    """
    try:
        return ph.verify(hash_value, api_key)
    except argon2.exceptions.VerifyMismatchError:
        return False
    except Exception:
        logger.exception("Ошибка при проверке API ключа")
        return False


# ========== Функция генерации API-ключей ==========


def generate_api_key() -> tuple[str, str]:
    """
    Генерирует безопасный случайный API ключ.

    Returns:
        Кортеж (полный_api_ключ, префикс_ключа)
        API ключ в формате 'sk_live_' + 32 случайных символа (base64)
    """
    random_str = secrets.token_urlsafe(24)
    full_key = f"sk_live_{random_str}"
    # Префикс: первые 8 символов после sk_live_ для быстрого поиска
    prefix = random_str[:8]
    return full_key, prefix


# ========== AuthService ==========


class AuthService:
    """Сервис аутентификации."""

    def __init__(self, session: AsyncSession | None = None):
        """
        Инициализация сервиса.

        Args:
            session: Асинхронная сессия SQLAlchemy. Если не передана, создается новая.
        """
        self.session = session

    async def _get_session(self) -> AsyncSession:
        """Получает сессию для работы с БД."""
        if self.session is not None:
            return self.session
        return AsyncSessionLocal()

    # ========== Методы работы с пользователями ==========

    async def create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """
        Создает нового пользователя.

        Args:
            telegram_id: ID пользователя в Telegram
            username: Имя пользователя в Telegram (опционально)
            first_name: Имя пользователя (опционально)
            last_name: Фамилия пользователя (опционально)

        Returns:
            Созданный пользователь

        Raises:
            SQLAlchemyError: При ошибках работы с БД
        """
        async with await self._get_session() as session:
            try:
                # Проверяем, существует ли пользователь
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    logger.info(
                        "Пользователь с telegram_id %d уже существует", telegram_id
                    )
                    return existing_user

                # Создаем нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                # Создаем политику ротации по умолчанию для пользователя
                default_policy = APIKeyRotationPolicy(
                    user_id=user.id,
                    key_lifetime_days=90,
                    auto_rotate=True,
                    rotate_before_days=7,
                )
                session.add(default_policy)

                await session.commit()

                logger.info(
                    "Создан пользователь: %d (telegram_id: %d) с политикой ротации",
                    user.id,
                    telegram_id,
                )
                return user

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Ошибка при создании пользователя")
                raise

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        """
        Получает пользователя по Telegram ID.

        Args:
            telegram_id: ID пользователя в Telegram

        Returns:
            Пользователь или None если не найден
        """
        async with await self._get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        """
        Получает пользователя по внутреннему ID.

        Args:
            user_id: Внутренний ID пользователя

        Returns:
            Пользователь или None если не найден
        """
        async with await self._get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    # ========== Методы работы с API-ключами ==========

    async def create_api_key(
        self,
        user_id: int,
        name: str | None = None,
        expires_days: int | None = None,
    ) -> str:
        """
        Создает новый API ключ для пользователя.

        Args:
            user_id: ID пользователя
            name: Название ключа (опционально)
            expires_days: Срок действия в днях (опционально)

        Returns:
            Созданный API ключ (открытый ключ, возвращается только один раз!)

        Raises:
            ValueError: Если пользователь не найден
            SQLAlchemyError: При ошибках работы с БД
        """
        async with await self._get_session() as session:
            try:
                # Проверяем существование пользователя
                user = await session.get(User, user_id)
                if not user:
                    msg = f"Пользователь с ID {user_id} не найден"
                    raise ValueError(msg)

                # Генерируем API ключ и префикс
                api_key, key_prefix = generate_api_key()
                api_key_hash = hash_api_key(api_key)

                # Вычисляем дату истечения
                expires_at = None
                if expires_days:
                    expires_at = datetime.now(UTC) + timedelta(days=expires_days)

                # Создаем запись API ключа
                api_key_record = UserAPIKey(
                    user_id=user_id,
                    api_key_hash=api_key_hash,
                    key_prefix=key_prefix,
                    name=name,
                    expires_at=expires_at,
                    is_active=True,
                )
                session.add(api_key_record)
                await session.commit()
                await session.refresh(api_key_record)

                logger.info(
                    "Создан API ключ для пользователя %d: id=%d, prefix=%s",
                    user_id,
                    api_key_record.id,
                    key_prefix,
                )
                return api_key

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Ошибка при создании API ключа")
                raise

    async def verify_api_key(self, api_key: str) -> User | None:
        """
        Проверяет API ключ и возвращает соответствующего пользователя.

        Использует prefix-based lookup для эффективного поиска ключа.
        Формат ключа: sk_live_<prefix><rest>, где prefix = первые 8 символов.

        Args:
            api_key: API ключ для проверки

        Returns:
            Пользователь если ключ валиден, иначе None
        """
        async with await self._get_session() as session:
            try:
                # Извлекаем префикс из ключа
                # Формат: sk_live_<prefix><rest>
                if not api_key.startswith("sk_live_"):
                    logger.warning("Неверный формат API ключа")
                    return None

                # Префикс - первые 8 символов после sk_live_
                # Всего в random_str 24 символа (32 base64), берем первые 8
                key_without_prefix = api_key[8:]  # Убираем sk_live_
                key_prefix = key_without_prefix[:8]

                if not key_prefix:
                    logger.warning("API ключ слишком короткий")
                    return None

                # Ищем ключи с данным префиксом (используем индекс)
                result = await session.execute(
                    select(UserAPIKey).where(
                        UserAPIKey.key_prefix == key_prefix,
                        UserAPIKey.is_active,
                        or_(
                            UserAPIKey.expires_at.is_(None),
                            UserAPIKey.expires_at > datetime.now(UTC),
                        ),
                    )
                )
                api_keys = result.scalars().all()

                # Проверяем только найденные ключи (обычно 1-2)
                for key_record in api_keys:
                    if verify_api_key(api_key, key_record.api_key_hash):
                        # Обновляем last_used_at
                        key_record.last_used_at = datetime.now(UTC)
                        await session.commit()

                        # Получаем пользователя
                        user = await session.get(User, key_record.user_id)
                        if user and user.is_active:
                            return user
                        return None

                logger.debug("Ключ с префиксом %s не найден или невалиден", key_prefix)
                return None

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Ошибка при проверке API ключа")
                return None

    async def get_user_api_keys(self, user_id: int) -> list[UserAPIKey]:
        """
        Получает список API ключей пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список API ключей пользователя
        """
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserAPIKey)
                .where(UserAPIKey.user_id == user_id)
                .order_by(UserAPIKey.created_at.desc())
            )
            return list(result.scalars().all())

    async def deactivate_api_key(self, key_id: int) -> bool:
        """
        Деактивирует API ключ.

        Args:
            key_id: ID API ключа

        Returns:
            True если ключ успешно деактивирован, иначе False
        """
        async with await self._get_session() as session:
            try:
                result = await session.execute(
                    select(UserAPIKey).where(UserAPIKey.id == key_id)
                )
                api_key = result.scalar_one_or_none()

                if not api_key:
                    return False

                api_key.is_active = False
                await session.commit()

                logger.info("Деактивирован API ключ: id=%s", key_id)
                return True

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Ошибка при деактивации API ключа")
                return False

    async def get_rotation_policy(
        self, user_id: int, session: AsyncSession | None = None
    ) -> APIKeyRotationPolicy:
        """
        Получает политику ротации для пользователя.
        Приоритет: персональная политика > глобальная (user_id IS NULL) > дефолтная.

        Args:
            user_id: ID пользователя
            session: Внешняя сессия БД (опционально). Если передана, используется она.

        Returns:
            Политика ротации (создает дефолтную если не найдена)
        """
        if session is not None:
            return await self._get_rotation_policy_internal(user_id, session)

        async with await self._get_session() as session:
            return await self._get_rotation_policy_internal(user_id, session)

    async def _get_rotation_policy_internal(
        self, user_id: int, session: AsyncSession
    ) -> APIKeyRotationPolicy:
        """Внутренняя реализация получения политики ротации."""
        # Сначала ищем персональную политику
        result = await session.execute(
            select(APIKeyRotationPolicy).where(APIKeyRotationPolicy.user_id == user_id)
        )
        policy = result.scalar_one_or_none()

        if policy:
            return policy

        # Ищем глобальную политику (user_id IS NULL)
        result = await session.execute(
            select(APIKeyRotationPolicy).where(APIKeyRotationPolicy.user_id.is_(None))
        )
        policy = result.scalar_one_or_none()

        if policy:
            return policy

        # Создаем дефолтную глобальную политику если нет ни одной
        default_policy = APIKeyRotationPolicy(
            user_id=None,
            key_lifetime_days=90,
            auto_rotate=True,
            rotate_before_days=7,
        )
        session.add(default_policy)
        await session.commit()
        await session.refresh(default_policy)

        logger.info("Создана дефолтная политика ротации: id=%d", default_policy.id)
        return default_policy

    async def rotate_api_key(
        self, key_id: int, key_lifetime_days: int | None = None
    ) -> str | None:
        """
        Ротирует API ключ: создает новый ключ и деактивирует старый.

        Args:
            key_id: ID API ключа для ротации
            key_lifetime_days: Срок действия нового ключа в днях.
                Если не указан, берется из политики ротации пользователя.

        Returns:
            Новый API ключ или None если ключ не найден или неактивен
        """
        async with await self._get_session() as session:
            try:
                # Находим старый ключ
                result = await session.execute(
                    select(UserAPIKey).where(
                        UserAPIKey.id == key_id, UserAPIKey.is_active
                    )
                )
                old_key = result.scalar_one_or_none()

                if not old_key:
                    logger.warning(
                        "Ключ для ротации не найден или неактивен: key_id=%d", key_id
                    )
                    return None

                # Получаем политику ротации если lifetime не указан
                if key_lifetime_days is None:
                    policy = await self.get_rotation_policy(old_key.user_id)
                    key_lifetime_days = policy.key_lifetime_days

                # Создаем новый ключ с префиксом
                new_api_key, new_key_prefix = generate_api_key()
                new_api_key_hash = hash_api_key(new_api_key)

                # Вычисляем дату истечения нового ключа
                expires_at = datetime.now(UTC) + timedelta(days=key_lifetime_days)

                # Создаем новый ключ
                new_key_record = UserAPIKey(
                    user_id=old_key.user_id,
                    api_key_hash=new_api_key_hash,
                    key_prefix=new_key_prefix,
                    name=old_key.name,
                    expires_at=expires_at,
                    is_active=True,
                    rotated_from_id=old_key.id,
                )
                session.add(new_key_record)

                # Деактивируем старый ключ
                old_key.is_active = False

                await session.commit()
                await session.refresh(new_key_record)

                logger.info(
                    "Ротирован API ключ: old_id=%d, new_id=%d, prefix=%s, expires_at=%s, lifetime_days=%d",
                    key_id,
                    new_key_record.id,
                    new_key_prefix,
                    expires_at.isoformat(),
                    key_lifetime_days,
                )
                return new_api_key

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Ошибка при ротации API ключа")
                return None

    # ========== Методы работы с JWT сессиями ==========

    def _create_token(self, user_id: int, token_type: str = "access") -> str:
        """
        Создает JWT токен.

        Args:
            user_id: ID пользователя
            token_type: Тип токена ('access' или 'refresh')

        Returns:
            JWT токен
        """
        now = datetime.now(UTC)

        if token_type == "access":
            expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        elif token_type == "refresh":
            expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        else:
            msg = f"Неизвестный тип токена: {token_type}"
            raise ValueError(msg)

        payload = {
            "sub": str(user_id),
            "type": token_type,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def create_session(self, user_id: int) -> tuple[str, str]:
        """
        Создает новую сессию (access и refresh токены).

        Args:
            user_id: ID пользователя

        Returns:
            Кортеж (access_token, refresh_token)
        """
        access_token = self._create_token(user_id, "access")
        refresh_token = self._create_token(user_id, "refresh")

        # Сохраняем refresh токен в БД
        async with await self._get_session() as session:
            try:
                # Удаляем старые сессии пользователя (опционально)
                await session.execute(
                    select(TelegramSession).where(TelegramSession.user_id == user_id)
                )

                # Создаем новую сессию
                expires_at = datetime.now(UTC) + timedelta(
                    days=settings.REFRESH_TOKEN_EXPIRE_DAYS
                )
                session_record = TelegramSession(
                    user_id=user_id,
                    token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                )
                session.add(session_record)
                await session.commit()

                logger.info("Создана сессия для пользователя %s", user_id)
                return access_token, refresh_token

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Ошибка при создании сессии")
                raise

    async def refresh_session(self, refresh_token: str) -> tuple[str, str] | None:
        """
        Обновляет сессию по refresh токену.

        Args:
            refresh_token: Refresh токен

        Returns:
            Кортеж (новый_access_token, новый_refresh_token) или None если
            токен невалиден
        """
        try:
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )

            if payload.get("type") != "refresh":
                logger.warning("Неверный тип токена для refresh")
                return None

            user_id = int(payload["sub"])

            # Проверяем, что refresh токен существует в БД
            async with await self._get_session() as session:
                result = await session.execute(
                    select(TelegramSession).where(
                        TelegramSession.refresh_token == refresh_token,
                        TelegramSession.user_id == user_id,
                        TelegramSession.expires_at > datetime.now(UTC),
                    )
                )
                session_record = result.scalar_one_or_none()

                if not session_record:
                    return None

                # Создаем новые токены
                return await self.create_session(user_id)

        except JWTError:
            logger.warning("Ошибка при декодировании refresh токена")
            return None

    async def verify_token(self, token: str) -> User | None:
        """
        Проверяет JWT токен и возвращает пользователя.

        Args:
            token: JWT токен

        Returns:
            Пользователь если токен валиден, иначе None
        """
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )

            user_id = int(payload["sub"])
            token_type = payload.get("type")

            if token_type not in ["access", "refresh"]:
                return None

            # Проверяем, что токен есть в БД (опционально, для отзыва)
            # Примечание: Для access токенов проверка в БД опциональна для производительности.
            # Это означает, что отозванные access токены будут работать до истечения срока.
            # Для строгой проверки (например, при отзыве токена) нужно проверять refresh токен
            # или добавить токен в blacklist.
            async with await self._get_session() as session:
                result = await session.execute(
                    select(TelegramSession).where(
                        TelegramSession.token == token,
                        TelegramSession.user_id == user_id,
                        TelegramSession.expires_at > datetime.now(UTC),
                    )
                )
                session_record = result.scalar_one_or_none()

                if not session_record and token_type == "access":
                    # Для access токена проверка в БД опциональна (fail-open для производительности)
                    # Но пользователь должен существовать и быть активным
                    user = await session.get(User, user_id)
                    if user and user.is_active:
                        return user
                    return None

                if session_record:
                    user = await session.get(User, user_id)
                    if user and user.is_active:
                        return user

                return None

        except JWTError:
            logger.warning("Ошибка при верификации токена")
            return None
