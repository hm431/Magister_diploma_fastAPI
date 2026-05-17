from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.mtr import SupplyPlanResponse, WarehouseFeasibilityResponse
from app.services.supply_plan import run_supply_plan
from app.services.warehouse_feasibility import run_warehouse_feasibility

router = APIRouter()


@router.post(
    "/supply-plan/{project_id}/{calculation_id}",
    response_model=SupplyPlanResponse,
    summary="2.1 — График поставок материалов (LP, formulas 2.8–2.18)",
)
async def supply_plan(
    project_id: int,
    calculation_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(get_current_user),
) -> SupplyPlanResponse:
    """
    Рассчитывает суточную потребность Q_{jt} (2.9),
    решает транспортную LP-задачу x_{jlt} → min F1 (2.13–2.17),
    сохраняет результат в mtr.material_demand, mtr.planned_delivery,
    mtr.material_availability_date.
    """
    return await run_supply_plan(project_id, calculation_id, session)


@router.post(
    "/warehouse-feasibility/{project_id}/{calculation_id}",
    response_model=WarehouseFeasibilityResponse,
    summary="2.2 — Проверка загрузки склада и логистики (M/M/n, formulas 2.19–2.30)",
)
async def warehouse_feasibility(
    project_id: int,
    calculation_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(get_current_user),
) -> WarehouseFeasibilityResponse:
    """
    Строит потоковую модель склада U_t (2.19–2.23),
    применяет модель M/M/n: ρ(t), L_q(t), W_q(t) (2.25–2.30).
    При нарушениях выполняет итеративную корректировку плана поставок (2.24)
    и сохраняет профиль в mtr.warehouse_load_profile.
    """
    return await run_warehouse_feasibility(project_id, calculation_id, session)
