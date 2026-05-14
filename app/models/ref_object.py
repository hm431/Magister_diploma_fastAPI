from typing import Optional

from sqlalchemy import String, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class ObjectRef(Base):
    """ref.object — объекты строительства."""
    __tablename__ = "object"
    __table_args__ = {"schema": "ref"}

    object_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_start: Mapped[Optional[Date]] = mapped_column(Date)
    planned_finish: Mapped[Optional[Date]] = mapped_column(Date)

    sites = relationship("Site", back_populates="object")
    projects = relationship("Project", back_populates="object")


class Site(Base):
    """ref.site — строительные участки."""
    __tablename__ = "site"
    __table_args__ = {"schema": "ref"}

    site_id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("ref.object.object_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    object = relationship("ObjectRef", back_populates="sites")


class WorkType(Base):
    """ref.work_type — типы СМР."""
    __tablename__ = "work_type"
    __table_args__ = {"schema": "ref"}

    work_type_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)