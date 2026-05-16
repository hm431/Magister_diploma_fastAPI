from __future__ import annotations
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric
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
