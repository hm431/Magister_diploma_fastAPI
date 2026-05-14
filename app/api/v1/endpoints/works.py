from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class WorkOut(BaseModel):
    id: int
    project_id: int
    name: str
    duration_days: int
    predecessors: List[int]
    status: str


class WorkCreate(BaseModel):
    project_id: int
    name: str
    duration_days: int
    predecessors: List[int] = []


class WorkUpdate(BaseModel):
    name: Optional[str] = None
    duration_days: Optional[int] = None
    predecessors: Optional[List[int]] = None
    status: Optional[str] = None


_STUB = WorkOut(id=1, project_id=1, name="Земляные работы", duration_days=10, predecessors=[], status="planned")


@router.get("/", response_model=List[WorkOut], summary="Список работ проекта")
async def list_works(project_id: int):
    return [_STUB]


@router.post("/", response_model=WorkOut, status_code=201, summary="Создать работу")
async def create_work(body: WorkCreate):
    return WorkOut(id=2, project_id=body.project_id, name=body.name, duration_days=body.duration_days, predecessors=body.predecessors, status="planned")


@router.get("/{work_id}", response_model=WorkOut, summary="Получить работу")
async def get_work(work_id: int):
    return WorkOut(id=work_id, project_id=1, name="Заглушка", duration_days=5, predecessors=[], status="planned")


@router.patch("/{work_id}", response_model=WorkOut, summary="Обновить работу")
async def update_work(work_id: int, body: WorkUpdate):
    return WorkOut(id=work_id, project_id=1, name=body.name or "Заглушка", duration_days=body.duration_days or 5, predecessors=body.predecessors or [], status=body.status or "planned")


@router.delete("/{work_id}", status_code=204, summary="Удалить работу")
async def delete_work(work_id: int):
    return None
