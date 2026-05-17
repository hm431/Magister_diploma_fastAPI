from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.risk import MonteCarloRequest, MonteCarloResponse
from app.services.risk_service import run_monte_carlo

router = APIRouter()


# ---------------------------------------------------------------------------
# Стабы — базовый CRUD рисков (будет расширен отдельной задачей)
# ---------------------------------------------------------------------------

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


_STUB = RiskOut(
    id=1, project_id=1, name="Задержка поставок",
    probability=0.4, impact=0.7, risk_score=0.28,
    category="МТО", mitigation="Предварительные заказы за 4 недели", status="active",
)


@router.get("/", response_model=List[RiskOut], summary="Список рисков проекта")
async def list_risks(project_id: int):
    return [_STUB]


@router.post("/", response_model=RiskOut, status_code=201, summary="Добавить риск")
async def create_risk(body: RiskCreate):
    score = round(body.probability * body.impact, 4)
    return RiskOut(
        id=2, project_id=body.project_id, name=body.name,
        probability=body.probability, impact=body.impact, risk_score=score,
        category=body.category, mitigation=body.mitigation, status="active",
    )


@router.get("/{risk_id}", response_model=RiskOut, summary="Получить риск")
async def get_risk(risk_id: int):
    return _STUB.model_copy(update={"id": risk_id})


@router.patch("/{risk_id}", response_model=RiskOut, summary="Обновить риск")
async def update_risk(risk_id: int, body: RiskCreate):
    score = round(body.probability * body.impact, 4)
    return RiskOut(
        id=risk_id, project_id=body.project_id, name=body.name,
        probability=body.probability, impact=body.impact, risk_score=score,
        category=body.category, mitigation=body.mitigation, status="active",
    )


@router.delete("/{risk_id}", status_code=204, summary="Удалить риск")
async def delete_risk(risk_id: int):
    return None


@router.get("/matrix/{project_id}", response_model=List[RiskMatrixItem], summary="Матрица рисков проекта")
async def get_risk_matrix(project_id: int):
    return [RiskMatrixItem(risk_id=1, risk_name="Задержка поставок", probability=0.4, impact=0.7, level="high")]


# ---------------------------------------------------------------------------
# Задача 3 — Имитационная модель оценки рисков (Монте-Карло, формулы 2.39–2.50)
# ---------------------------------------------------------------------------

@router.post(
    "/monte-carlo/{project_id}",
    response_model=MonteCarloResponse,
    summary="3 — Имитационная оценка рисков срыва сроков (Монте-Карло, formulas 2.39–2.50)",
)
async def monte_carlo_risk(
    project_id: int,
    body: MonteCarloRequest,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(get_current_user),
) -> MonteCarloResponse:
    """
    Запускает R итераций Монте-Карло для проекта project_id.

    - Шаг 1–2: вычисляет / дополняет Beta-параметры (2.39–2.41) и LogN-параметры τ_jk (2.42–2.44).
    - Шаг 3: создаёт запись в risk.monte_carlo_run.
    - Шаг 4: параллельный прямой + обратный проход CPM с ресурсным ограничением (2.1–2.2, 2.6, 2.45).
    - Шаг 5: P(T ≤ T_план) (2.46), E[T] (2.47), σ[T] (2.48).
    - Шаг 6: квантили T_0.5, T_0.8, T_0.9 (2.49) → risk.risk_quantile.
    - Шаг 7: индексы критичности CI_i (2.50) → risk.work_criticality_index.

    Ответ содержит run_id, статистику, топ-10 риск-критичных работ и S-кривую (эмпирическую ФРВ).
    """
    return await run_monte_carlo(project_id, body, session)
