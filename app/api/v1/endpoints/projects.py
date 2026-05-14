from __future__ import annotations

from datetime import date
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ProjectOut(BaseModel):
    id: int
    name: str
    address: str
    start_date: date
    end_date: date
    status: str


class ProjectCreate(BaseModel):
    name: str
    address: str
    start_date: date
    end_date: date


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    end_date: Optional[date] = None
    status: Optional[str] = None


_STUB = ProjectOut(id=1, name="Водоканал объект №1", address="г. Тюмень, ул. Ленина 1", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31), status="active")


@router.get("/", response_model=List[ProjectOut], summary="Список проектов")
async def list_projects():
    return [_STUB]


@router.post("/", response_model=ProjectOut, status_code=201, summary="Создать проект")
async def create_project(body: ProjectCreate):
    return ProjectOut(id=2, name=body.name, address=body.address, start_date=body.start_date, end_date=body.end_date, status="draft")


@router.get("/{project_id}", response_model=ProjectOut, summary="Получить проект")
async def get_project(project_id: int):
    return ProjectOut(id=project_id, name="Заглушка", address="г. Тюмень", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31), status="active")


@router.patch("/{project_id}", response_model=ProjectOut, summary="Обновить проект")
async def update_project(project_id: int, body: ProjectUpdate):
    return ProjectOut(id=project_id, name=body.name or "Заглушка", address=body.address or "г. Тюмень", start_date=date(2025, 1, 1), end_date=body.end_date or date(2025, 12, 31), status=body.status or "active")


@router.delete("/{project_id}", status_code=204, summary="Удалить проект")
async def delete_project(project_id: int):
    return None
