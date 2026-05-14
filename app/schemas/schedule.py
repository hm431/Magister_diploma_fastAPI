from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ScheduleItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    work_id: int
    es: int
    ef: int
    ls: int
    lf: int
    tf: int
    is_critical: bool


class ScheduleCalculationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calculation_id: int
    project_id: int
    calculation_date: datetime
    version: int
    scenario: str
    t_min: Optional[int]
    items: List[ScheduleItemRead]