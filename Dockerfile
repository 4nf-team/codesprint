# Multi-stage Dockerfile для production

# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание виртуального окружения
RUN python -m venv /app/.venv

# Активация виртуального окружения
ENV PATH="/app/.venv/bin:$PATH"

# Копирование файлов зависимостей
COPY pyproject.toml uv.lock README.md ./

# Установка зависимостей через pip
RUN pip install --no-cache-dir .

# Stage 2: Production
FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей для runtime
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование виртуального окружения из builder
COPY --from=builder /app/.venv /app/.venv

# Активация виртуального окружения
ENV PATH="/app/.venv/bin:$PATH"

# Копирование исходного кода
COPY app ./app
COPY scripts ./scripts
COPY alembic ./alembic
COPY pyproject.toml ./

# Создание необходимых директорий
RUN mkdir -p /app/logs /app/models /app/backups

# Создание non-root пользователя
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app

# Экспорт переменных окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
