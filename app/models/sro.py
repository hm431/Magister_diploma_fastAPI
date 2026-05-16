from __future__ import annotations
from datetime import date
from typing import Optional, List

from sqlalchemy import Integer, String, Date, ForeignKey, Numeric, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Project(Base):
    """sro.project — проект строительства."""
    __tablename__ = "project"
    __table_args__ = {"schema": "sro"}

    project_id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("ref.object.object_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="planned")
    plan_start: Mapped[date] = mapped_column(Date, nullable=False)
    plan_finish: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start: Mapped[Optional[date]] = mapped_column(Date)
    actual_finish: Mapped[Optional[date]] = mapped_column(Date)

    object = relationship("ObjectRef", back_populates="projects")
    works = relationship("Work", back_populates="project", cascade="all, delete-orphan")
    calculations = relationship(
        "ScheduleCalculation", back_populates="project", cascade="all, delete-orphan"
    )


class Work(Base):
    """sro.work — работа проекта (узел сетевой модели)."""
    __tablename__ = "work"
    __table_args__ = {"schema": "sro"}

    work_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("sro.project.project_id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("ref.site.site_id"), nullable=False)
    work_type_id: Mapped[int] = mapped_column(ForeignKey("ref.work_type.work_type_id"), nullable=False)

    duration: Mapped[int] = mapped_column(Integer, nullable=False)               # d_i
    volume: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)        # v_i
    required_qualification_id: Mapped[Optional[int]] = mapped_column(Integer)
    required_equipment_type: Mapped[Optional[str]] = mapped_column(String(100))

    project = relationship("Project", back_populates="works")
    work_type = relationship("WorkType")
    site = relationship("Site")

    # Предшественники (множество P_i)
    predecessors = relationship(
        "WorkPredecessor",
        foreign_keys="WorkPredecessor.work_id",
        back_populates="work",
        cascade="all, delete-orphan",
    )


class WorkPredecessor(Base):
    """sro.work_predecessor — технологические зависимости."""
    __tablename__ = "work_predecessor"
    __table_args__ = {"schema": "sro"}

    work_id: Mapped[int] = mapped_column(
        ForeignKey("sro.work.work_id"), primary_key=True
    )
    predecessor_work_id: Mapped[int] = mapped_column(
        ForeignKey("sro.work.work_id"), primary_key=True
    )

    work = relationship("Work", foreign_keys=[work_id], back_populates="predecessors")
    predecessor = relationship("Work", foreign_keys=[predecessor_work_id])


class ScheduleCalculation(Base):
    """sro.schedule_calculation — запуск расчёта календарного графика."""
    __tablename__ = "schedule_calculation"
    __table_args__ = {"schema": "sro"}

    calculation_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("sro.project.project_id"), nullable=False)
    calculation_date: Mapped[date] = mapped_column(DateTime, server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1)
    t_min: Mapped[Optional[int]] = mapped_column(Integer)               # формула (2.7)
    scenario: Mapped[str] = mapped_column(String(50), default="plan")

    project = relationship("Project", back_populates="calculations")
    items = relationship(
        "ScheduleItem", back_populates="calculation", cascade="all, delete-orphan"
    )
    brigade_assignments = relationship(
        "BrigadeAssignment", back_populates="calculation", cascade="all, delete-orphan"
    )


class ScheduleItem(Base):
    """sro.schedule_item — параметры одной работы в расчёте: ES, EF, LS, LF, TF."""
    __tablename__ = "schedule_item"
    __table_args__ = {"schema": "sro"}

    calculation_id: Mapped[int] = mapped_column(
        ForeignKey("sro.schedule_calculation.calculation_id"), primary_key=True
    )
    work_id: Mapped[int] = mapped_column(ForeignKey("sro.work.work_id"), primary_key=True)

    es: Mapped[int] = mapped_column(Integer, nullable=False)     # формула (2.1)
    ef: Mapped[int] = mapped_column(Integer, nullable=False)     # формула (2.2)
    ls: Mapped[int] = mapped_column(Integer, nullable=False)     # формула (2.4)
    lf: Mapped[int] = mapped_column(Integer, nullable=False)     # формула (2.3)
    tf: Mapped[int] = mapped_column(Integer, nullable=False)     # формула (2.5)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)

    calculation = relationship("ScheduleCalculation", back_populates="items")
    work = relationship("Work")


class BrigadeAssignment(Base):
    """sro.brigade_assignment — назначения бригад на участки (y_{ks}, формула 2.31)."""
    __tablename__ = "brigade_assignment"
    __table_args__ = {"schema": "sro"}

    assignment_id: Mapped[int] = mapped_column(primary_key=True)
    brigade_id: Mapped[int] = mapped_column(
        ForeignKey("ref.brigade.brigade_id"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(
        ForeignKey("ref.site.site_id"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    assignment_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    schedule_calculation_id: Mapped[int] = mapped_column(
        ForeignKey("sro.schedule_calculation.calculation_id"), nullable=False
    )

    calculation = relationship("ScheduleCalculation", back_populates="brigade_assignments")