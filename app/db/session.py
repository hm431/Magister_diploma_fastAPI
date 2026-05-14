"""
db/session.py

Асинхронный движок SQLAlchemy и фабрика сессий для работы с PostgreSQL.
Используется через FastAPI-зависимость get_db.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


# ============================================================
#  Асинхронный движок
#
#  Строка подключения должна быть формата:
#    postgresql+asyncpg://user:password@host:port/dbname
#
#  echo=True в dev — выводит SQL в лог, удобно для отладки расчётов.
#  В проде обязательно False, иначе логи распухнут.
#
#  pool_pre_ping=True — проверяет «живость» соединения перед использованием.
#  Защищает от обрывов после простоя (актуально для корпоративной сети,
#  где firewall может закрывать idle-соединения).
# ============================================================
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,           # True только в dev
    pool_pre_ping=True,
    pool_size=10,                    # базовый размер пула соединений
    max_overflow=20,                 # доп. соединения при пике нагрузки
                                     # → итого до 30 одновременных запросов к БД
                                     # (требование ТЗ: ≥50 пользователей)
    pool_recycle=3600,               # пересоздавать соединения раз в час
)


# ============================================================
#  Фабрика сессий
#
#  expire_on_commit=False — после commit() объекты остаются доступными.
#  Без этого FastAPI не сможет вернуть объект в ответе после сохранения
#  (получишь DetachedInstanceError при попытке прочитать его атрибуты).
# ============================================================
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ============================================================
#  FastAPI dependency
#
#  Использование в роуте:
#    @router.get("/projects/{id}")
#    async def get_project(id: int, session: AsyncSession = Depends(get_db)):
#        ...
#
#  Транзакционная семантика:
#   - при успехе → commit
#   - при исключении → rollback (try/except на стороне SQLAlchemy через
#     контекстный менеджер сессии)
#   - сессия гарантированно закрывается в finally
# ============================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Выдаёт сессию БД и автоматически закрывает её после запроса."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()