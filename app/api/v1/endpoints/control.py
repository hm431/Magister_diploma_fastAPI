from __future__ import annotations

from datetime import date
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ProgressUpdate(BaseModel):
    work_id: int
    actual_progress: float
    report_date: date
    note: str = ""


class DeviationOut(BaseModel):
    work_id: int
    work_name: str
    planned_progress: float
    actual_progress: float
    deviation: float
    status: str


class KPIOut(BaseModel):
    project_id: int
    spi: float
    cpi: float
    schedule_variance_days: int
    cost_variance_pct: float


@router.get("/progress/{project_id}", summary="Фактический прогресс по работам проекта")
async def get_progress(project_id: int, report_date: Optional[date] = None):
    return {
        "project_id": project_id,
        "report_date": str(report_date or date.today()),
        "overall_progress": 35.0,
        "works": [{"work_id": 1, "work_name": "Земляные работы", "progress": 100.0}],
    }


@router.post("/progress", summary="Внести фактический прогресс по работе")
async def update_progress(body: ProgressUpdate):
    return {"detail": "Прогресс обновлён (заглушка)", "work_id": body.work_id, "progress": body.actual_progress}


@router.get("/deviations/{project_id}", response_model=List[DeviationOut], summary="Отклонения план/факт")
async def get_deviations(project_id: int):
    return [DeviationOut(work_id=1, work_name="Монтаж трубопровода", planned_progress=60.0, actual_progress=45.0, deviation=-15.0, status="behind")]


@router.get("/kpi/{project_id}", response_model=KPIOut, summary="KPI проекта (SPI, CPI)")
async def get_kpi(project_id: int):
    return KPIOut(project_id=project_id, spi=0.85, cpi=0.92, schedule_variance_days=-7, cost_variance_pct=-4.5)


@router.get("/alerts/{project_id}", summary="Активные предупреждения по проекту")
async def get_alerts(project_id: int):
    return {
        "project_id": project_id,
        "alerts": [
            {"level": "warning", "message": "Работа 'Монтаж трубопровода' отстаёт от графика на 15%"},
            {"level": "info", "message": "Запасы цемента на складе ниже нормы"},
        ],
    }
