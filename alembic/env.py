import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Добавление корневого каталога в path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импортируем модели после определения Base
from app.models import database  # noqa: E402, PLC0415

target_metadata = database.Base.metadata

config = context.config

# Интерпретация конфигурационного файла
fileConfig(config.config_file_name)


def get_url():
    """Получение URL базы данных из настроек."""
    from app.core.config import settings  # noqa: PLC0415

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


def do_run_migrations(connection):
    """Выполнение миграций с синхронным подключением."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """Запуск миграций в асинхронном режиме."""
    url = get_url()

    # Создаём асинхронный движок
    engine = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online():
    """Запуск миграций в online режиме."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
