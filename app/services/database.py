"""CRUD операции с базой данных."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.database import (
    AnalysisTask,
    AsyncSessionLocal,
    Base,
    engine,
)

logger = get_logger(__name__)


async def init_db():
    """Инициализация базы данных (создание таблиц)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Закрытие соединения с БД."""
    await engine.dispose()


class DatabaseService:
    """
    Сервис для операций с базой данных.

    Каждый метод создает свою сессию для выполнения операции.

    Attributes:
        session: Асинхронная сессия SQLAlchemy (опционально)
    """

    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    async def check_connection(self) -> bool:
        """
        Проверка подключения к БД.

        Returns:
            True если подключение работает
        """
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(select(1))
            except Exception:
                logger.exception("Database connection check failed")
                return False
            else:
                return True

    async def create_analysis_task(self, user_id: str, image_hash: str) -> str:
        """
        Создание новой задачи анализа.

        Args:
            user_id: ID пользователя
            image_hash: Хэш изображения

        Returns:
            ID созданной задачи
        """
        async with AsyncSessionLocal() as session:
            task_id = str(uuid.uuid4())

            task = AnalysisTask(
                id=task_id, user_id=user_id, image_hash=image_hash, status="pending"
            )

            session.add(task)

            try:
                await session.commit()
                await session.refresh(task)
            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Failed to create analysis task")
                raise
            else:
                logger.info("Created analysis task %s for user %s", task_id, user_id)
                return task_id

    async def update_task_result(
        self, task_id: str, result: dict[str, Any], processing_time_ms: float
    ) -> bool:
        """
        Обновление результата задачи.

        Args:
            task_id: ID задачи
            result: Результат анализа
            processing_time_ms: Время обработки

        Returns:
            True если успешно
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    update(AnalysisTask)
                    .where(AnalysisTask.id == task_id)
                    .values(
                        status="completed",
                        result=result,
                        processing_time_ms=processing_time_ms,
                        completed_at=datetime.now(UTC),
                    )
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info("Updated task %s with result", task_id)
                    return True
                logger.warning("Task %s not found", task_id)
                return False

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Failed to update task %s", task_id)
                return False

    async def update_task_error(self, task_id: str, error_message: str) -> bool:
        """
        Обновление задачи с ошибкой.

        Args:
            task_id: ID задачи
            error_message: Сообщение об ошибке

        Returns:
            True если успешно
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    update(AnalysisTask)
                    .where(AnalysisTask.id == task_id)
                    .values(
                        status="failed",
                        error=error_message,
                        completed_at=datetime.now(UTC),
                    )
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info("Updated task %s with error", task_id)
                    return True
                return False

            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Failed to update task %s with error", task_id)
                return False

    async def get_analysis_result(self, task_id: str) -> dict[str, Any] | None:
        """
        Получение результата анализа по ID задачи.

        Args:
            task_id: ID задачи

        Returns:
            Результат или None
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(AnalysisTask).where(AnalysisTask.id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if task and task.status == "completed":
                    return {
                        "task_id": task.id,
                        "status": task.status,
                        "result": task.result,
                        "processing_time_ms": task.processing_time_ms,
                        "created_at": task.created_at.isoformat()
                        if task.created_at
                        else None,
                        "completed_at": task.completed_at.isoformat()
                        if task.completed_at
                        else None,
                    }

            except SQLAlchemyError:
                logger.exception("Failed to get task %s", task_id)
                return None
            else:
                return None

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        Получение статуса задачи по ID.

        Args:
            task_id: ID задачи

        Returns:
            Статус задачи или None
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(AnalysisTask).where(AnalysisTask.id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if task:
                    return {
                        "task_id": task.id,
                        "status": task.status,
                        "result": task.result,
                        "error": task.error,
                        "processing_time_ms": task.processing_time_ms,
                        "created_at": task.created_at.isoformat()
                        if task.created_at
                        else None,
                        "completed_at": task.completed_at.isoformat()
                        if task.completed_at
                        else None,
                    }

            except SQLAlchemyError:
                logger.exception("Failed to get task %s", task_id)
                return None
            else:
                return None

    async def get_user_tasks(
        self, user_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Получение задач пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество задач

        Returns:
            Список задач
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    select(AnalysisTask)
                    .where(AnalysisTask.user_id == user_id)
                    .order_by(AnalysisTask.created_at.desc())
                    .limit(limit)
                )

                result = await session.execute(stmt)
                tasks = result.scalars().all()

                return [
                    {
                        "task_id": task.id,
                        "status": task.status,
                        "created_at": task.created_at.isoformat()
                        if task.created_at
                        else None,
                        "processing_time_ms": task.processing_time_ms,
                    }
                    for task in tasks
                ]

            except SQLAlchemyError:
                logger.exception("Failed to get tasks for user %s", user_id)
                return []

    async def get_task_by_hash(
        self, image_hash: str, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Поиск завершенной задачи по хэшу изображения.

        Args:
            image_hash: Хэш изображения
            user_id: ID пользователя (опционально для ограничения поиска)

        Returns:
            Результат если найден
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(AnalysisTask).where(
                    AnalysisTask.image_hash == image_hash,
                    AnalysisTask.status == "completed",
                )

                if user_id:
                    stmt = stmt.where(AnalysisTask.user_id == user_id)

                stmt = stmt.order_by(AnalysisTask.completed_at.desc()).limit(1)

                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if task:
                    return task.result

            except SQLAlchemyError as e:
                logger.exception("Failed to get task by hash %s: %s", image_hash, e)
                return None
            else:
                return None
