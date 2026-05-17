from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MonteCarloRequest(BaseModel):
    iterations: int = Field(default=1000, ge=100, le=100_000, description="Число итераций R")
    seed: Optional[int] = Field(default=None, description="Seed для воспроизводимости")
    t_plan: float = Field(..., gt=0, description="Плановая продолжительность T_план (дни)")


class CriticalWorkItem(BaseModel):
    work_id: int
    criticality_index: float
    risk_critical: bool


class CDFPoint(BaseModel):
    t: float
    F: float


class MonteCarloResponse(BaseModel):
    run_id: int
    mean_duration: float           # E[T] — формула 2.47
    std_duration: float            # σ[T] — формула 2.48
    prob_on_time: float            # P(T ≤ T_план) — формула 2.46
    t_quantile_50: float           # T_0.5 — формула 2.49
    t_quantile_80: float           # T_0.8
    t_quantile_90: float           # T_0.9
    top_critical_works: List[CriticalWorkItem]  # топ-10 по CI_i
    cdf: List[CDFPoint]            # эмпирическая F_T(t) для S-кривой
