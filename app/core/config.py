"""Конфигурация приложения через Pydantic Settings."""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Настройки приложения.

    Все настройки могут быть переопределены через переменные окружения.
    """

    # Общие настройки
    PROJECT_NAME: str = "Image Analysis API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Security
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # API_KEY для development/testing.
    # В production должен быть установлен через env переменную.
    # Если API_KEY пустой, аутентификация через статический API-ключ отключена.
    API_KEY: str = ""
    API_KEY_HEADER: str = "X-API-Key"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_ANALYZE: str = "10/minute"
    RATE_LIMIT_FAIL_OPEN: bool = (
        False  # Блокировать запросы при недоступности Redis (безопаснее)
    )

    # CORS
    ALLOWED_ORIGINS: list[str] | str = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/image_analysis"
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 час

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ML Model
    MODEL_CONFIDENCE_THRESHOLD: float = 0.5
    MODEL_DEVICE: str = "cuda"  # или "cpu"

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    SENTRY_DSN: str | None = None
    GF_SECURITY_ADMIN_PASSWORD: str | None = None

    # File Upload
    MAX_IMAGE_SIZE_MB: int = 10
    ALLOWED_IMAGE_FORMATS: list[str] | str = ["JPEG", "PNG", "WEBP", "PDF"]

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBAPP_URL: str = ""

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Валидация критических настроек безопасности."""
        if not self.SECRET_KEY:
            if self.ENVIRONMENT == "production":
                msg = (
                    "SECRET_KEY must be set in production! "
                    "Set SECRET_KEY environment variable."
                )
                raise ValueError(msg)
            # Для development используем временный ключ
            self.SECRET_KEY = "dev-secret-key-do-not-use-in-production"
        return self

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list[str]) -> list[str]:
        """Parse ALLOWED_ORIGINS from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("ALLOWED_IMAGE_FORMATS", mode="before")
    @classmethod
    def parse_allowed_image_formats(cls, v: str | list[str]) -> list[str]:
        """Parse ALLOWED_IMAGE_FORMATS from comma-separated string or list."""
        if isinstance(v, str):
            return [fmt.strip() for fmt in v.split(",") if fmt.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()
