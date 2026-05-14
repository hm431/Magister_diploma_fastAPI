from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс для всех моделей приложения."""
    pass


class TimestampMixin:
    """Добавляет колонки created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Импорты моделей — нужны, чтобы Base.metadata знал обо всех таблицах
# при вызове create_all. По мере появления моделей дописывай сюда:
#
# from app.models.user import User, Role                   # noqa: F401
# from app.models.project import Project                   # noqa: F401
# from app.models.work import Work, WorkDependency         # noqa: F401
# ...