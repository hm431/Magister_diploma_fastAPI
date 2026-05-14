from __future__ import annotations

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class RiskOut(BaseModel):
    id: int
    project_id: int
    name: str
    probability: float
    impact: float
    risk_score: float
    category: str
    mitigation: str
    status: str


class RiskCreate(BaseModel):
    project_id: int
    name: str
    probability: float
    impact: float
    category: str
    mitigation: str = ""


class RiskMatrixItem(BaseModel):
    risk_id: int
    risk_name: str
    probability: float
    impact: float
    level: str


_STUB = RiskOut(id=1, project_id=1, name="Задержка поставок", probability=0.4, impact=0.7, risk_score=0.28, category="МТО", mitigation="Предварительные заказы за 4 недели", status="active")


@router.get("/", response_model=List[RiskOut], summary="Список рисков проекта")
async def list_risks(project_id: int):
    return [_STUB]


@router.post("/", response_model=RiskOut, status_code=201, summary="Добавить риск")
async def create_risk(body: RiskCreate):
    score = round(body.probability * body.impact, 4)
    return RiskOut(id=2, project_id=body.project_id, name=body.name, probability=body.probability, impact=body.impact, risk_score=score, category=body.category, mitigation=body.mitigation, status="active")


@router.get("/{risk_id}", response_model=RiskOut, summary="Получить риск")
async def get_risk(risk_id: int):
    return _STUB.model_copy(update={"id": risk_id})


@router.patch("/{risk_id}", response_model=RiskOut, summary="Обновить риск")
async def update_risk(risk_id: int, body: RiskCreate):
    score = round(body.probability * body.impact, 4)
    return RiskOut(id=risk_id, project_id=body.project_id, name=body.name, probability=body.probability, impact=body.impact, risk_score=score, category=body.category, mitigation=body.mitigation, status="active")


@router.delete("/{risk_id}", status_code=204, summary="Удалить риск")
async def delete_risk(risk_id: int):
    return None


@router.get("/matrix/{project_id}", response_model=List[RiskMatrixItem], summary="Матрица рисков проекта")
async def get_risk_matrix(project_id: int):
    return [RiskMatrixItem(risk_id=1, risk_name="Задержка поставок", probability=0.4, impact=0.7, level="high")]


@router.post("/analyze/{project_id}", summary="Провести анализ рисков (Monte Carlo)")
async def analyze_risks(project_id: int, simulations: int = 1000):
    return {
        "project_id": project_id,
        "simulations": simulations,
        "p50_duration": 125,
        "p80_duration": 140,
        "p95_duration": 155,
        "detail": "Анализ рисков выполнен (заглушка)",
    }
