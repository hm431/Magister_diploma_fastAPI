from __future__ import annotations
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


# ─── Подзадача 2.1: График поставок ────────────────────────────────────────

class DemandRow(BaseModel):
    material_id: int
    demand_date: date
    quantity: float


class DeliveryRow(BaseModel):
    material_id: int
    warehouse_id: int
    supplier_id: int
    planned_date: date
    planned_volume: float
    unit_cost: float


class AvailabilityRow(BaseModel):
    material_id: int
    availability_date: date


class SupplyPlanResponse(BaseModel):
    project_id: int
    calculation_id: int
    total_cost: float                       # F1 = sum(c_jlt * x_jlt)
    demand: List[DemandRow]                 # Q_jt по дням
    deliveries: List[DeliveryRow]           # x_jlt > 0
    availability: List[AvailabilityRow]     # T_доступ(j) по материалам
    solver_status: str


# ─── Подзадача 2.2: Проверка склада ────────────────────────────────────────

class LoadProfileRow(BaseModel):
    profile_date: date
    total_load: float
    utilization_ratio: float                # U_t / U_max
    peak_indicator: bool
    queue_length: Optional[float]
    wait_time: Optional[float]
    rho: Optional[float]                    # ρ(t) — загрузка системы


class ViolationRow(BaseModel):
    profile_date: date
    violation_type: str                     # "capacity" | "overload" | "wait_time"
    description: str


class WarehouseFeasibilityResponse(BaseModel):
    project_id: int
    calculation_id: int
    warehouse_id: int
    feasible: bool
    violations: List[ViolationRow]
    load_profile: List[LoadProfileRow]
    adjusted_deliveries: Optional[List[DeliveryRow]]
