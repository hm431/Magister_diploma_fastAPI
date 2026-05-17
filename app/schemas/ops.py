from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, model_validator


class RecalculateRequest(BaseModel):
    t_0: date
    beta1: float   # вес критерия ΔT
    beta2: float   # вес критерия ΔC
    beta3: float   # вес критерия ΔR

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "RecalculateRequest":
        total = round(self.beta1 + self.beta2 + self.beta3, 6)
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"beta1 + beta2 + beta3 должна равняться 1.0, получено {total}")
        return self


class DeviationCauseItem(BaseModel):
    material_id: int
    supplier_id: Optional[int]
    deficit_volume: float


class DeviationItem(BaseModel):
    work_id: int
    plan_percent: float
    fact_percent: float
    delta_percent: float
    chi_mtr: bool
    category: str
    causes: List[DeviationCauseItem] = []


class ScheduleItemActual(BaseModel):
    work_id: int
    es: int    # дней от plan_start
    ef: int
    ls: int
    lf: int
    tf: int
    is_critical: bool


class ScenarioResult(BaseModel):
    scenario_type: str   # 'sigma1' | 'sigma2' | 'sigma3'
    delta_t: float       # ΔT(σ), дней
    delta_c: float       # ΔC(σ)
    delta_r: float       # ΔR(σ)
    j_score: float       # J(σ)
    is_optimal: bool     # σ*


class RecalculateResponse(BaseModel):
    project_id: int
    calculation_id: int
    t_plan: int                        # T_план, дней от plan_start
    t_actual: float                    # T^акт(t_0)
    delta_t: float                     # ΔT(t_0) = T^акт − T_план
    delta_t_mtr: float                 # ΔT^МТР(t_0)
    delta_t_other: float               # ΔT^иные(t_0)
    deviations: List[DeviationItem]
    schedule: List[ScheduleItemActual]
    scenarios: List[ScenarioResult]
