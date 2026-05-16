from __future__ import annotations
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BrigadeAssignmentRequest(BaseModel):
    """Веса целевой функции (2.35) и ограничения на число бригад на участке."""
    alpha1: float = Field(default=0.5, ge=0.0, le=1.0, description="Вес штрафа за квалификацию")
    alpha2: float = Field(default=0.3, ge=0.0, le=1.0, description="Вес транспортной стоимости")
    alpha3: float = Field(default=0.2, ge=0.0, le=1.0, description="Вес необеспеченности материалами")
    n_min: int = Field(default=1, ge=0, description="Минимальное число бригад на участке")
    n_max: int = Field(default=3, ge=1, description="Максимальное число бригад на участке")

    @model_validator(mode="after")
    def alphas_must_sum_to_one(self) -> "BrigadeAssignmentRequest":
        total = self.alpha1 + self.alpha2 + self.alpha3
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"alpha1 + alpha2 + alpha3 должны быть равны 1.0, получено {total:.6f}")
        return self


class AssignmentItem(BaseModel):
    """Одно назначение бригады на участок (y_{ks} = 1)."""
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    brigade_id: int
    site_id: int
    period_start: date
    period_end: date
    assignment_cost: Optional[float]


class SiteProvisionRate(BaseModel):
    """Коэффициент обеспеченности участка материалами m_s (формула 2.36)."""
    site_id: int
    m_s: float


class BrigadeAssignmentResult(BaseModel):
    """Результат решения задачи распределения бригад (формулы 2.31–2.37)."""
    calculation_id: int
    objective_value: float
    assignments: List[AssignmentItem]
    provision_rates: List[SiteProvisionRate]
