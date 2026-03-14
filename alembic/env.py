import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Добавление корневого каталога в path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

config = context.config

# Интерпретация конфигурационного файла
fileConfig(config.config_file_name)

# Импорт моделей
from app.models.database import Base

target_metadata = Base.metadata


def get_url():
    """Получение URL базы данных из настроек."""
    from app.core.config import settings

    return settings.DATABASE_URL


def run_migrations_offline():
    """Запуск миграций в offline режиме."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Запуск миграций в online режиме."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
