# Image Analysis API

Высокопроизводительный REST API сервис для анализа изображений на основе глубокого обучения.

## Особенности

- **FastAPI** - современный высокопроизводительный веб-фреймворк
- **PyTorch/YOLOv5** - детекция объектов на изображениях
- **PostgreSQL** - хранение результатов и метаданных
- **Redis** - кэширование результатов и брокер сообщений для Celery
- **Celery** - асинхронная обработка задач
- **Docker** - контейнеризация и оркестрация
- **Nginx** - reverse proxy и балансировщик нагрузки
- **Prometheus + Grafana** - мониторинг и метрики
- **Асинхронная архитектура** - высокая производительность и масштабируемость

## Быстрый старт

## Требования к системе

### Аппаратные требования
- **Минимальные**: 2 CPU cores, 4 GB RAM
- **Рекомендуемые**: 4+ CPU cores, 8+ GB RAM
- **Для GPU**: NVIDIA GPU с CUDA 11.x+ (опционально)

### Программные требования
- Docker & Docker Compose (для контейнеризации)
- Python 3.11+ (для локальной разработки)
- PostgreSQL 15+ (уже в контейнере)
- Redis 7+ (уже в контейнере)

### Поддерживаемые форматы изображений
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)

### Ограничения
- Максимальный размер файла: 10 MB
- Максимальное разрешение: 4096x4096

### Запуск в Docker (Production)

```bash
# Клонирование репозитория
git clone <repository-url>
cd codesprint

# Копирование конфигурации
cp .env.example .env
# Отредактируйте .env при необходимости

# Сборка и запуск всех сервисов
docker-compose up -d --build

# Проверка статуса контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f app

# Проверка здоровья сервиса
curl http://localhost/api/v1/health
```

#### Доступные сервисы после запуска

| Сервис | URL | Описание |
|--------|-----|----------|
| FastAPI | http://localhost:8000 | Основное API |
| Swagger UI | http://localhost:8000/docs | Интерактивная документация |
| ReDoc | http://localhost:8000/redoc | Альтернативная документация |
| Prometheus | http://localhost:9090 | Метрики |
| Grafana | http://localhost:3000 | Дашборды (admin/admin) |
| Nginx | http://localhost | Reverse proxy |
| Node Exporter | http://localhost:9100 | Метрики хоста |
| cAdvisor | http://localhost:8080 | Метрики контейнеров |

#### Остановка сервисов

```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением томов
docker-compose down -v

# Остановка с удалением образов
docker-compose down --rmi all
```

### Запуск в development режиме

```bash
# Установка зависимостей
pip install -e ".[dev]"

# Настройка переменных окружения
cp .env.example .env

# Запуск базы данных и Redis (через Docker Compose)
docker-compose up -d postgres redis

# Инициализация БД
python scripts/init_db.py

# Запуск приложения
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# В другом терминале - запуск Celery worker
celery -A app.workers.celery_app worker --loglevel=info

# И запуск Celery beat для периодических задач
celery -A app.workers.celery_app beat --loglevel=info
```

## API Documentation

После запуска приложения:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health
- **Metrics**: http://localhost:8000/api/v1/metrics

### Основные эндпоинты

#### 1. Анализ изображения

Анализирует загруженное изображение с помощью YOLOv5 модели.

```http
POST /api/v1/analyze
Content-Type: multipart/form-data
X-API-Key: your-api-key

file: <image file>
```

**Параметры:**
- `file` (required): Файл изображения (JPEG, PNG, WebP)

**Заголовки:**
- `X-API-Key` (required): API ключ для аутентификации

**Ответ:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Задача поставлена в очередь"
}
```

#### 2. Получение статуса задачи

Возвращает текущий статус задачи анализа.

```http
GET /api/v1/tasks/{task_id}
X-API-Key: your-api-key
```

**Параметры пути:**
- `task_id` (required): UUID задачи

**Ответ (в процессе):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Статус: STARTED"
}
```

**Ответ (завершено):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "objects": [
      {
        "label": "person",
        "confidence": 0.95,
        "bbox": {"x": 100.0, "y": 50.0, "width": 200.0, "height": 300.0}
      }
    ],
    "metadata": {
      "processing_time_ms": 150.5,
      "model_version": "yolov5s-v1.0",
      "image_size": {"width": 640, "height": 480},
      "timestamp": "2024-01-15T10:30:00Z"
    },
    "cached": false
  },
  "message": "Анализ завершен"
}
```

#### 3. Получение результата анализа

Возвращает результаты завершённого анализа.

```http
GET /api/v1/result/{task_id}
X-API-Key: your-api-key
```

**Параметры пути:**
- `task_id` (required): UUID задачи

**Ответ:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "objects": [
    {
      "label": "person",
      "confidence": 0.95,
      "bbox": {"x": 100.0, "y": 50.0, "width": 200.0, "height": 300.0}
    }
  ],
  "metadata": {
    "processing_time_ms": 150.5,
    "model_version": "yolov5s-v1.0",
    "image_size": {"width": 640, "height": 480},
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "cached": false
}
```

#### 4. Health Check

Проверка здоровья сервиса и его зависимостей.

```http
GET /api/v1/health
```

**Ответ:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "services": {
    "database": true,
    "cache": true,
    "model": true,
    "queue": true
  }
}
```

#### 5. Readiness Check

Проверка готовности принимать трафик.

```http
GET /api/v1/health/ready
```

**Ответ:**
```json
{
  "ready": true
}
```

#### 6. Liveness Check

Проверка что приложение работает.

```http
GET /api/v1/health/live
```

**Ответ:**
```json
{
  "alive": true
}
```

#### 7. Метрики Prometheus

```http
GET /api/v1/metrics
```

Возвращает метрики в формате Prometheus.

### Примеры использования

#### cURL

```bash
# Анализ изображения
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "X-API-Key: dev-api-key-12345" \
  -F "file=@image.jpg"

# Проверка статуса
curl -X GET "http://localhost:8000/api/v1/tasks/{task_id}" \
  -H "X-API-Key: dev-api-key-12345"

# Получение результата
curl -X GET "http://localhost:8000/api/v1/result/{task_id}" \
  -H "X-API-Key: dev-api-key-12345"
```

#### Python

```python
import requests

API_KEY = "dev-api-key-12345"
BASE_URL = "http://localhost:8000/api/v1"

headers = {"X-API-Key": API_KEY}

# Загрузка изображения на анализ
with open("image.jpg", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/analyze",
        files={"file": f},
        headers=headers
    )
    task_id = response.json()["task_id"]

# Проверка статуса
response = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
print(response.json())

# Получение результата
response = requests.get(f"{BASE_URL}/result/{task_id}", headers=headers)
print(response.json())
```

## Структура проекта

```
codesprint/
├── app/
│   ├── api/              # API роутеры и эндпоинты
│   │   ├── v1/
│   │   │   ├── endpoints/    # Эндпоинты
│   │   │   ├── schemas/      # Pydantic схемы
│   │   │   └── deps.py       # Зависимости
│   ├── core/             # Ядро приложения
│   │   ├── config.py     # Настройки
│   │   ├── security.py   # Безопасность
│   │   └── logging.py    # Логирование
│   ├── models/           # SQLAlchemy модели
│   ├── services/         # Бизнес-логика
│   ├── ml/               # ML компоненты
│   ├── workers/          # Celery задачи
│   └── middleware/       # Middleware
├── tests/                # Тесты
├── scripts/              # Скрипты для управления
├── docker/               # Docker конфигурации
├── alembic/              # Миграции БД
├── docker-compose.yml    # Оркестрация сервисов
├── Dockerfile           # Multi-stage build
└── pyproject.toml       # Зависимости
```

## Конфигурация

Настройки через переменные окружения (см. [`.env.example`](.env.example)):

### Основные настройки
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PROJECT_NAME` | Название сервиса | Image Analysis API |
| `VERSION` | Версия API | 1.0.0 |
| `DEBUG` | Режим отладки | False |
| `ENVIRONMENT` | Окружение | production |

### API настройки
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `API_KEY` | Секретный ключ API | changeme |
| `API_KEY_HEADER` | Заголовок для API ключа | X-API-Key |
| `RATE_LIMIT_ENABLED` | Включить rate limiting | True |
| `RATE_LIMIT_DEFAULT` | Лимит по умолчанию | 100/minute |
| `RATE_LIMIT_ANALYZE` | Лимит для анализа | 10/minute |

### База данных
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | URL подключения к PostgreSQL | postgresql+asyncpg://postgres:postgres@localhost:5432/image_analysis |
| `DATABASE_POOL_SIZE` | Размер пула соединений | 20 |
| `DATABASE_MAX_OVERFLOW` | Максимальное переполнение пула | 10 |

### Redis
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `REDIS_URL` | URL подключения к Redis | redis://localhost:6379/0 |
| `REDIS_CACHE_TTL` | TTL кэша в секундах | 3600 |

### Celery
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `CELERY_BROKER_URL` | URL брокера сообщений | redis://localhost:6379/1 |
| `CELERY_RESULT_BACKEND` | URL бэкенда результатов | redis://localhost:6379/2 |

### ML Модель
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `MODEL_PATH` | Путь к файлу модели | /app/models/yolov5s.pt |
| `MODEL_CONFIDENCE_THRESHOLD` | Порог уверенности | 0.5 |
| `MODEL_DEVICE` | Устройство для инференса (cuda/cpu) | cuda |

### Загрузка файлов
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `MAX_IMAGE_SIZE_MB` | Максимальный размер файла (MB) | 10 |
| `ALLOWED_IMAGE_FORMATS` | Разрешённые форматы | JPEG,PNG,WEBP |

### Мониторинг и логирование
| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `LOG_LEVEL` | Уровень логирования | INFO |
| `LOG_FORMAT` | Формат логов (json/text) | json |
| `PROMETHEUS_ENABLED` | Включить метрики Prometheus | True |
| `SENTRY_DSN` | DSN для Sentry (опционально) | - |

## Мониторинг

Сервисы мониторинга доступны через Docker Compose:

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Метрики приложения**: http://localhost:8000/api/v1/metrics

## Разработка

### Запуск тестов

```bash
pytest tests/ -v
```

### Генерация миграций

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Форматирование кода

```bash
black app/ tests/
ruff check app/ tests/ --fix
mypy app/
```

## Производительность

- **Кэширование**: Redis кэш для повторяющихся запросов
- **Очереди задач**: Celery для асинхронной обработки
- **Rate limiting**: Защита от перегрузок
- **Connection pooling**: Оптимизация подключений к БД
- **GPU поддержка**: Возможность использования CUDA

## Безопасность

- API Key аутентификация
- Rate limiting на уровне приложения
- CORS настройки
- Защита от распространенных атак
- HTTPS в production (через Nginx)

## Лицензия

MIT
