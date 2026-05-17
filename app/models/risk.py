from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class WorkRiskParams(Base):
    """risk.work_risk_params — PERT-тройки и параметры Beta-распределения (формулы 2.39–2.41)."""

    __tablename__ = "work_risk_params"
    __table_args__ = {"schema": "risk"}

    work_id: Mapped[int] = mapped_column(ForeignKey("sro.work.work_id"), primary_key=True)
    a_i: Mapped[float] = mapped_column(Float, nullable=False)              # оптимистичная оценка
    m_i: Mapped[float] = mapped_column(Float, nullable=False)              # наиболее вероятная
    b_i: Mapped[float] = mapped_column(Float, nullable=False)              # пессимистичная
    alpha: Mapped[Optional[float]] = mapped_column(Float)                  # α Beta — формула 2.41
    beta_param: Mapped[Optional[float]] = mapped_column("beta", Float)     # β Beta — формула 2.41
    expected_duration: Mapped[Optional[float]] = mapped_column(Float)      # E[d_i] — формула 2.39
    std_deviation: Mapped[Optional[float]] = mapped_column(Float)          # σ[d_i] — формула 2.40


class SupplierDeliveryStats(Base):
    """risk.supplier_delivery_stats — параметры LogN срока поставки τ_jk (формулы 2.42–2.44)."""

    __tablename__ = "supplier_delivery_stats"
    __table_args__ = {"schema": "risk"}

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("ref.supplier.supplier_id"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("ref.material.material_id"), primary_key=True
    )
    mu_jk: Mapped[float] = mapped_column(Float, nullable=False)     # параметр μ логнормального
    sigma_jk: Mapped[float] = mapped_column(Float, nullable=False)  # параметр σ логнормального
    sample_size: Mapped[int] = mapped_column(Integer, default=0)    # объём выборки


class MonteCarloRun(Base):
    """risk.monte_carlo_run — запись о запуске имитационного моделирования."""

    __tablename__ = "monte_carlo_run"
    __table_args__ = {"schema": "risk"}

    run_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("sro.project.project_id"), nullable=False
    )
    iterations_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[Optional[int]] = mapped_column(Integer)
    t_plan: Mapped[float] = mapped_column(Float, nullable=False)            # T_план
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    mean_duration: Mapped[Optional[float]] = mapped_column(Float)           # E[T] — формула 2.47
    std_duration: Mapped[Optional[float]] = mapped_column(Float)            # σ[T] — формула 2.48
    prob_on_time: Mapped[Optional[float]] = mapped_column(Float)            # P(T≤T_план) — формула 2.46


class MonteCarloIteration(Base):
    """risk.monte_carlo_iteration — результат одной итерации: T^(r), C^(r) (формула 2.45)."""

    __tablename__ = "monte_carlo_iteration"
    __table_args__ = {"schema": "risk"}

    run_id: Mapped[int] = mapped_column(
        ForeignKey("risk.monte_carlo_run.run_id"), primary_key=True
    )
    iteration_num: Mapped[int] = mapped_column(Integer, primary_key=True)
    t_result: Mapped[float] = mapped_column(Float, nullable=False)          # T^(r)
    critical_path: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer))  # C^(r)


class RiskQuantile(Base):
    """risk.risk_quantile — квантили T_γ продолжительности проекта (формула 2.49)."""

    __tablename__ = "risk_quantile"
    __table_args__ = {"schema": "risk"}

    run_id: Mapped[int] = mapped_column(
        ForeignKey("risk.monte_carlo_run.run_id"), primary_key=True
    )
    gamma_level: Mapped[float] = mapped_column(Float, primary_key=True)    # 0.5 / 0.8 / 0.9
    t_gamma: Mapped[float] = mapped_column(Float, nullable=False)


class WorkCriticalityIndex(Base):
    """risk.work_criticality_index — индекс критичности CI_i (формула 2.50)."""

    __tablename__ = "work_criticality_index"
    __table_args__ = {"schema": "risk"}

    run_id: Mapped[int] = mapped_column(
        ForeignKey("risk.monte_carlo_run.run_id"), primary_key=True
    )
    work_id: Mapped[int] = mapped_column(ForeignKey("sro.work.work_id"), primary_key=True)
    criticality_index: Mapped[float] = mapped_column(Float, nullable=False)  # CI_i = count(i∈C^r)/R
    risk_critical: Mapped[bool] = mapped_column(Boolean, default=False)       # CI_i > 0.5
