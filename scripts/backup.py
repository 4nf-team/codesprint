#!/usr/bin/env python3
"""Создание резервной копии базы данных."""

import asyncio
import sys
import subprocess
from datetime import datetime
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()


async def backup_database():
    """
    Создание резервной копии PostgreSQL базы данных.
    """
    print("Starting database backup...")

    # Парсинг DATABASE_URL
    # Формат: postgresql://user:password@host:port/dbname
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        # Удаляем префикс postgresql://
        conn_str = db_url.replace("postgresql://", "")
    elif db_url.startswith("postgresql+asyncpg://"):
        conn_str = db_url.replace("postgresql+asyncpg://", "")
    else:
        print(f"Unsupported database URL format: {db_url}")
        sys.exit(1)

    # Разбор строки подключения
    parts = conn_str.split("@")
    if len(parts) != 2:
        print("Invalid database URL format")
        sys.exit(1)

    user_pass = parts[0].split(":")
    host_port_db = parts[1].split("/")

    if len(user_pass) != 2 or len(host_port_db) < 2:
        print("Invalid database URL format")
        sys.exit(1)

    user = user_pass[0]
    password = user_pass[1]
    host_port = host_port_db[0].split(":")
    host = host_port[0]
    port = host_port[1] if len(host_port) > 1 else "5432"
    dbname = host_port_db[1]

    # Создание директории для бэкапов
    backup_dir = root_dir / "backups"
    backup_dir.mkdir(exist_ok=True)

    # Имя файла бэкапа
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{dbname}_{timestamp}.sql"

    # Установка переменной окружения для пароля
    env = {"PGPASSWORD": password}

    # Команда pg_dump
    cmd = [
        "pg_dump",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        dbname,
        "-f",
        str(backup_file),
        "--no-owner",
        "--no-privileges",
    ]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, env=env, check=True, capture_output=True, text=True
        )
        print(f"Backup created successfully: {backup_file}")
        print(f"Size: {backup_file.stat().st_size} bytes")
        return str(backup_file)
    except subprocess.CalledProcessError as e:
        print(f"Backup failed: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("pg_dump not found. Please install PostgreSQL client tools.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(backup_database())
