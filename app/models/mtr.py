from __future__ import annotations
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class StockBalance(Base):
    """mtr.stock_balance — остатки материалов на складах (V_{jt}, формула 2.10)."""
    __tablename__ = "stock_balance"
    __table_args__ = {"schema": "mtr"}

    stock_id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("ref.material.material_id"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("ref.warehouse.warehouse_id"), nullable=False
    )
    balance_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    reserved_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)


class MaterialDemand(Base):
    """mtr.material_demand — плановая потребность Q_{jt} (формула 2.9)."""
    __tablename__ = "material_demand"
    __table_args__ = {"schema": "mtr"}

    project_id: Mapped[int] = mapped_column(
        ForeignKey("sro.project.project_id"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("ref.material.material_id"), primary_key=True
    )
    demand_date: Mapped[date] = mapped_column(Date, primary_key=True)
    schedule_calculation_id: Mapped[int] = mapped_column(
        ForeignKey("sro.schedule_calculation.calculation_id"), primary_key=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)


class PlannedDelivery(Base):
    """mtr.planned_delivery — плановые поставки x_{jlt} (формула 2.12)."""
    __tablename__ = "planned_delivery"
    __table_args__ = {"schema": "mtr"}

    planned_delivery_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("sro.project.project_id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("ref.material.material_id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ref.warehouse.warehouse_id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("ref.supplier.supplier_id"), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_volume: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="planned")


class MaterialAvailabilityDate(Base):
    """mtr.material_availability_date — T_доступ(j) (формула 2.18)."""
    __tablename__ = "material_availability_date"
    __table_args__ = {"schema": "mtr"}

    project_id: Mapped[int] = mapped_column(ForeignKey("sro.project.project_id"), primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("ref.material.material_id"), primary_key=True)
    calculation_id: Mapped[int] = mapped_column(
        ForeignKey("sro.schedule_calculation.calculation_id"), primary_key=True
    )
    availability_date: Mapped[date] = mapped_column(Date, nullable=False)


class ActualDelivery(Base):
    """mtr.actual_delivery — фактические поставки P_jt^факт (КС-6)."""
    __tablename__ = "actual_delivery"
    __table_args__ = {"schema": "mtr"}

    delivery_id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("ref.material.material_id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ref.warehouse.warehouse_id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("ref.supplier.supplier_id"), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_volume: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)


class StockMovement(Base):
    """mtr.stock_movement — фактический расход материалов Q_jt^факт; отрицательный quantity = расход."""
    __tablename__ = "stock_movement"
    __table_args__ = {"schema": "mtr"}

    movement_id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("ref.material.material_id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ref.warehouse.warehouse_id"), nullable=False)
    work_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sro.work.work_id"))
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)


class WarehouseLoadProfile(Base):
    """mtr.warehouse_load_profile — U_t, L_q, W_q (формулы 2.22, 2.28, 2.29)."""
    __tablename__ = "warehouse_load_profile"
    __table_args__ = {"schema": "mtr"}

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("ref.warehouse.warehouse_id"), primary_key=True
    )
    profile_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_load: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    peak_indicator: Mapped[bool] = mapped_column(Boolean, default=False)
    queue_length: Mapped[Optional[float]] = mapped_column(Numeric(8, 3))
    wait_time: Mapped[Optional[float]] = mapped_column(Numeric(8, 3))
