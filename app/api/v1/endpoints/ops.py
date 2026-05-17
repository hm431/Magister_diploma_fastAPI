from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.ops import RecalculateRequest, RecalculateResponse
from app.services.ops_service import recalculate_project

router = APIRouter()


@router.post(
    "/recalculate/{project_id}",
    response_model=RecalculateResponse,
    summary="4 — Динамический пересчёт сроков по фактическим данным (formulas 2.51–2.64)",
)
async def recalculate(
    project_id: int,
    body: RecalculateRequest,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(get_current_user),
) -> RecalculateResponse:
    """
    Пересчитывает календарный график на основе фактических данных по состоянию на t_0.

    - Шаг 1: плановый процент выполнения p_i^план(t_0) — формула 2.52.
    - Шаг 2: Δp_i и классификация χ_i^МТР — формулы 2.51, 2.53; сохраняет ops.deviation.
    - Шаг 3: остаточная длительность d_i^ост через фактическую производительность — формулы 2.54–2.56.
    - Шаг 4: обновлённые T_доступ^факт(j) по фактическим остаткам и подтверждённым поставкам — формула 2.18.
    - Шаг 5: прямой и обратный проходы сетевой модели → T^акт(t_0), ΔT(t_0) — формулы 2.57–2.60.
    - Шаг 6: контрфактический проход → ΔT^МТР, ΔT^иные — формулы 2.61–2.62.
    - Шаг 7: сценарии σ_1 (ускорение поставок), σ_2 (перераспределение бригад),
      σ_3 (параллельные работы), оценка J(σ) = β1·ΔT + β2·ΔC + β3·ΔR,
      выбор σ* = argmin J — формулы 2.63–2.64; сохраняет ops.correction_scenario.
    - Шаг 8: сохраняет sro.schedule_calculation (scenario='actual') с обновлёнными schedule_item;
      обновляет risk.supplier_delivery_stats (μ_jk, σ²_jk).
    """
    return await recalculate_project(project_id, body, session)
