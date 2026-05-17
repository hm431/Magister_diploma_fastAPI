from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.sro import ScheduleCalculation
from app.schemas.schedule import ScheduleCalculationRead
from app.services.cpm import calculate_and_save_cpm
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.post(
    "/{project_id}",
    response_model=ScheduleCalculationRead,
    summary="Запустить расчёт календарного графика по методу CPM",
)
async def calculate_schedule(
    project_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Реализует формулы (2.1)-(2.5). Сохраняет новую версию расчёта."""
    calc = await calculate_and_save_cpm(project_id, session)
    # Дозагружаем items для ответа
    await session.refresh(calc, ["items"])
    return calc


@router.get(
    "/{project_id}/latest",
    response_model=ScheduleCalculationRead,
    summary="Получить последний расчёт календарного графика",
)
async def get_latest_schedule(
    project_id: int,
    scenario: str = "plan",
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(ScheduleCalculation)
        .where(
            ScheduleCalculation.project_id == project_id,
            ScheduleCalculation.scenario == scenario,
        )
        .order_by(ScheduleCalculation.version.desc())
        .options(selectinload(ScheduleCalculation.items))
        .limit(1)
    )
    calc = (await session.scalars(query)).first()
    if not calc:
        raise NotFoundError(message=f"Расчётов для проекта {project_id} не найдено")
    return calc