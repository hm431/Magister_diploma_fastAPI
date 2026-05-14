from __future__ import annotations

from datetime import date
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class WorkScheduleItem(BaseModel):
    work_id: int
    work_name: str
    early_start: date
    early_finish: date
    late_start: date
    late_finish: date
    total_float: int
    is_critical: bool


class ScheduleOut(BaseModel):
    project_id: int
    calculated_at: str
    duration_days: int
    critical_path: list[int]
    works: list[WorkScheduleItem]


class ResourceLevelingRequest(BaseModel):
    project_id: int
    max_workers: int = 10


@router.get("/{project_id}", response_model=ScheduleOut, summary="Получить календарный график проекта")
async def get_schedule(project_id: int):
    stub_work = WorkScheduleItem(
        work_id=1, work_name="Земляные работы",
        early_start=date(2025, 1, 1), early_finish=date(2025, 1, 10),
        late_start=date(2025, 1, 1), late_finish=date(2025, 1, 10),
        total_float=0, is_critical=True,
    )
    return ScheduleOut(project_id=project_id, calculated_at="2025-01-01T00:00:00", duration_days=120, critical_path=[1], works=[stub_work])


@router.post("/{project_id}/calculate", response_model=ScheduleOut, summary="Рассчитать КГ методом CPM")
async def calculate_schedule(project_id: int):
    stub_work = WorkScheduleItem(
        work_id=1, work_name="Земляные работы",
        early_start=date(2025, 1, 1), early_finish=date(2025, 1, 10),
        late_start=date(2025, 1, 1), late_finish=date(2025, 1, 10),
        total_float=0, is_critical=True,
    )
    return ScheduleOut(project_id=project_id, calculated_at="2025-01-01T00:00:00", duration_days=120, critical_path=[1], works=[stub_work])


@router.post("/{project_id}/level-resources", summary="Выровнять ресурсы (RCPSP)")
async def level_resources(project_id: int, body: ResourceLevelingRequest):
    return {"detail": "Выравнивание ресурсов выполнено (заглушка)", "project_id": project_id}


@router.get("/{project_id}/gantt", summary="Данные для диаграммы Ганта")
async def get_gantt(project_id: int):
    return {
        "project_id": project_id,
        "tasks": [
            {"id": 1, "name": "Земляные работы", "start": "2025-01-01", "end": "2025-01-10", "progress": 0, "dependencies": []},
            {"id": 2, "name": "Фундамент", "start": "2025-01-11", "end": "2025-01-25", "progress": 0, "dependencies": [1]},
        ],
    }
