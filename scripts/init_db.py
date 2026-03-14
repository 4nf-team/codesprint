#!/usr/bin/env python3
"""Инициализация базы данных."""

import asyncio
import sys
from pathlib import Path

from app.core.logging import configure_logging
from app.models.database import close_db, init_db

# Добавление корневого каталога в path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


configure_logging()


async def main():
    """Основная функция инициализации БД."""
    print("Initializing database...")
    try:
        await init_db()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        sys.exit(1)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
