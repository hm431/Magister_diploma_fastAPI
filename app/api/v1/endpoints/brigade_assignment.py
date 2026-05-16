from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.brigade_assignment import BrigadeAssignmentRequest, BrigadeAssignmentResult
from app.services.brigade_assignment import assign_brigades

router = APIRouter()


@router.post(
    "/brigade-assignment/{calculation_id}",
    response_model=BrigadeAssignmentResult,
    summary="Распределить бригады по строительным участкам (подзадача 1.2)",
)
async def run_brigade_assignment(
    calculation_id: int,
    body: BrigadeAssignmentRequest = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Решает задачу о назначениях (формулы 2.31–2.37):

    - Шаг 1: коэффициент обеспеченности m_s (формула 2.36)
    - Шаг 2: матрица стоимостей c_ks (формула 2.35)
    - Шаг 3: венгерский алгоритм (`scipy.optimize.linear_sum_assignment`)
    - Шаг 4: сохранение в `sro.brigade_assignment`

    Возвращает назначения y_{ks}, значение F3 и m_s по каждому участку.
    """
    if body is None:
        body = BrigadeAssignmentRequest()
    return await assign_brigades(calculation_id, body, session)
