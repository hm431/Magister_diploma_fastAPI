from __future__ import annotations
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class BrigadeQualification(Base):
    """norm.brigade_qualification — квалификации бригад (многие-ко-многим)."""
    __tablename__ = "brigade_qualification"
    __table_args__ = {"schema": "norm"}

    brigade_id: Mapped[int] = mapped_column(
        ForeignKey("ref.brigade.brigade_id"), primary_key=True
    )
    qualification_id: Mapped[int] = mapped_column(
        ForeignKey("ref.qualification.qualification_id"), primary_key=True
    )

    brigade: Mapped["Brigade"] = relationship(  # noqa: F821
        "Brigade", back_populates="qualifications"
    )


class ConsumptionNorm(Base):
    """norm.consumption_norm — нормы расхода материалов r_{ij} (формула 2.9)."""
    __tablename__ = "consumption_norm"
    __table_args__ = {"schema": "norm"}

    work_type_id: Mapped[int] = mapped_column(
        ForeignKey("ref.work_type.work_type_id"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("ref.material.material_id"), primary_key=True
    )
    effective_from: Mapped[date] = mapped_column(Date, primary_key=True)
    norm_value: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)


class SupplyContract(Base):
    """norm.supply_contract — договоры поставки (c_{jlt}, τ_{jl}^мин, W_{jl})."""
    __tablename__ = "supply_contract"
    __table_args__ = {"schema": "norm"}

    contract_id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("ref.supplier.supplier_id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("ref.material.material_id"), nullable=False)
    price_per_unit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)     # c_{jlt}
    min_delivery_days: Mapped[int] = mapped_column(Integer, nullable=False)            # τ_{jl}^мин
    max_volume_per_period: Mapped[Optional[float]] = mapped_column(Numeric(12, 3))     # W_{jl}
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)


class TransportParam(Base):
    """norm.transport_param — параметры транспортной доставки (q_{jl}, формула 2.25)."""
    __tablename__ = "transport_param"
    __table_args__ = {"schema": "norm"}

    material_id: Mapped[int] = mapped_column(
        ForeignKey("ref.material.material_id"), primary_key=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("ref.warehouse.warehouse_id"), primary_key=True
    )
    avg_capacity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)   # q_{jl}
    avg_delivery_time: Mapped[int] = mapped_column(Integer, nullable=False)
