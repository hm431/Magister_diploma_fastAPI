from __future__ import annotations
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class WorkProgress(Base):
    """ops.work_progress — фактический прогресс работы p_i^факт(t_0) и ES_i^факт из КС-6."""
    __tablename__ = "work_progress"
    __table_args__ = {"schema": "ops"}

    work_id: Mapped[int] = mapped_column(ForeignKey("sro.work.work_id"), primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    fact_percent: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)   # p_i^факт ∈ [0, 1]
    fact_es: Mapped[Optional[date]] = mapped_column(Date)                         # ES_i^факт


class Deviation(Base):
    """ops.deviation — отклонение хода работ (формулы 2.51–2.53)."""
    __tablename__ = "deviation"
    __table_args__ = {"schema": "ops"}

    deviation_id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("sro.work.work_id"), nullable=False)
    calculation_id: Mapped[int] = mapped_column(
        ForeignKey("sro.schedule_calculation.calculation_id"), nullable=False
    )
    detection_date: Mapped[date] = mapped_column(Date, nullable=False)             # t_0
    plan_percent: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)     # p_i^план
    fact_percent: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)     # p_i^факт
    delta_percent: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)    # Δp_i = plan − fact
    chi_mtr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # χ_i^МТР
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")


class DeviationCause(Base):
    """ops.deviation_cause — дефицитный материал и поставщик, ставший причиной МТР-отклонения."""
    __tablename__ = "deviation_cause"
    __table_args__ = {"schema": "ops"}

    cause_id: Mapped[int] = mapped_column(primary_key=True)
    deviation_id: Mapped[int] = mapped_column(
        ForeignKey("ops.deviation.deviation_id"), nullable=False
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("ref.material.material_id"), nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ref.supplier.supplier_id"))
    deficit_volume: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)


class CorrectionScenario(Base):
    """ops.correction_scenario — корректирующий сценарий σ и его оценка J(σ) (формулы 2.63–2.64)."""
    __tablename__ = "correction_scenario"
    __table_args__ = {"schema": "ops"}

    scenario_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("sro.project.project_id"), nullable=False)
    calculation_id: Mapped[int] = mapped_column(
        ForeignKey("sro.schedule_calculation.calculation_id"), nullable=False
    )
    detection_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(10), nullable=False)    # 'sigma1' / 'sigma2' / 'sigma3'
    delta_t: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)    # ΔT(σ), дней
    delta_c: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)    # ΔC(σ), денежных единиц
    delta_r: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)     # ΔR(σ), безразмерный
    j_score: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)    # J(σ) = β1·ΔT + β2·ΔC + β3·ΔR
    is_optimal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)   # σ*
