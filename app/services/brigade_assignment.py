"""
Распределение бригад по строительным участкам. Подзадача 1.2.
Формулы (2.31)–(2.37) из дипломной работы.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Dict, List, Set

import numpy as np
from scipy.optimize import linear_sum_assignment
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ScheduleCalculationError
from app.models.mtr import MaterialDemand, StockBalance
from app.models.norm import ConsumptionNorm
from app.models.ref_brigade import Brigade
from app.models.sro import BrigadeAssignment, ScheduleCalculation, ScheduleItem
from app.schemas.brigade_assignment import (
    AssignmentItem,
    BrigadeAssignmentRequest,
    BrigadeAssignmentResult,
    SiteProvisionRate,
)

# Штраф за несоответствие квалификации (h_ks при несовпадении)
_BIG_M = 1_000_000.0


async def assign_brigades(
    calculation_id: int,
    params: BrigadeAssignmentRequest,
    session: AsyncSession,
) -> BrigadeAssignmentResult:
    """
    Шаг 1: вычислить m_s (формула 2.36).
    Шаг 2: построить матрицу стоимостей c_ks (формула 2.35).
    Шаг 3: решить задачу о назначениях венгерским алгоритмом (формулы 2.31–2.37).
    Шаг 4: сохранить результат в sro.brigade_assignment.
    """
    # ── 1. Загрузка расчёта и проекта ──────────────────────────────────────
    calc = await session.get(ScheduleCalculation, calculation_id)
    if not calc:
        raise NotFoundError(message=f"Расчёт с id={calculation_id} не найден")

    from app.models.sro import Project  # локальный импорт — избегаем кругового
    project = await session.get(Project, calc.project_id)
    plan_start = project.plan_start

    # ── 2. Загрузка элементов расписания с работами ────────────────────────
    items_q = (
        select(ScheduleItem)
        .where(ScheduleItem.calculation_id == calculation_id)
        .options(selectinload(ScheduleItem.work))
    )
    items: List[ScheduleItem] = list((await session.scalars(items_q)).all())

    if not items:
        raise ScheduleCalculationError(message=f"Расчёт {calculation_id} не содержит работ")

    # ── 3. Группировка по участкам ─────────────────────────────────────────
    # site_id → {min_es, max_ef, required_quals, work_type_ids}
    site_data: Dict[int, dict] = {}
    for item in items:
        w = item.work
        sid = w.site_id
        if sid not in site_data:
            site_data[sid] = {
                "min_es": item.es,
                "max_ef": item.ef,
                "required_quals": set(),
                "work_type_ids": set(),
            }
        d = site_data[sid]
        d["min_es"] = min(d["min_es"], item.es)
        d["max_ef"] = max(d["max_ef"], item.ef)
        if w.required_qualification_id:
            d["required_quals"].add(w.required_qualification_id)
        d["work_type_ids"].add(w.work_type_id)

    site_ids = list(site_data.keys())

    # ── 4. Загрузка бригад с их квалификациями ─────────────────────────────
    brigades: List[Brigade] = list(
        (await session.scalars(
            select(Brigade).options(selectinload(Brigade.qualifications))
        )).all()
    )
    if not brigades:
        raise ScheduleCalculationError(message="В справочнике нет бригад для назначения")

    brigade_ids = [b.brigade_id for b in brigades]
    brigade_quals: Dict[int, Set[int]] = {
        b.brigade_id: {q.qualification_id for q in b.qualifications}
        for b in brigades
    }

    # ── 5. Нормы расхода: work_type_id → set material_id ──────────────────
    norm_rows = (await session.execute(
        select(ConsumptionNorm.work_type_id, ConsumptionNorm.material_id)
    )).all()

    wt_to_mats: Dict[int, Set[int]] = {}
    for wt_id, mat_id in norm_rows:
        wt_to_mats.setdefault(wt_id, set()).add(mat_id)

    # ── 6. Множество материалов J_s на каждом участке ─────────────────────
    site_materials: Dict[int, Set[int]] = {
        sid: set().union(*(wt_to_mats.get(wt, set()) for wt in d["work_type_ids"]))
        for sid, d in site_data.items()
    }
    all_mats: Set[int] = set().union(*site_materials.values()) if site_materials else set()

    # ── 7. Остатки V_j: суммарный доступный сток по последней дате ────────
    # (формула: V_js = quantity − reserved_quantity по всем складам)
    mat_stock: Dict[int, float] = {}
    if all_mats:
        latest_q = (
            select(
                StockBalance.material_id,
                func.max(StockBalance.balance_date).label("ld"),
            )
            .where(StockBalance.material_id.in_(all_mats))
            .group_by(StockBalance.material_id)
        )
        latest_dates = {r.material_id: r.ld for r in (await session.execute(latest_q)).all()}

        for mat_id, ld in latest_dates.items():
            val = (await session.execute(
                select(
                    func.sum(StockBalance.quantity - StockBalance.reserved_quantity)
                ).where(
                    StockBalance.material_id == mat_id,
                    StockBalance.balance_date == ld,
                )
            )).scalar() or 0.0
            mat_stock[mat_id] = max(0.0, float(val))

    # ── 8. Плановая потребность Q_j для данного расчёта ───────────────────
    mat_demand: Dict[int, float] = {}
    if all_mats:
        demand_rows = (await session.execute(
            select(
                MaterialDemand.material_id,
                func.sum(MaterialDemand.quantity).label("total"),
            )
            .where(
                MaterialDemand.schedule_calculation_id == calculation_id,
                MaterialDemand.material_id.in_(all_mats),
            )
            .group_by(MaterialDemand.material_id)
        )).all()
        for r in demand_rows:
            mat_demand[r.material_id] = float(r.total)

    # ── 9. Коэффициент обеспеченности m_s (формула 2.36) ──────────────────
    m_s: Dict[int, float] = {}
    for sid in site_ids:
        j_s = site_materials.get(sid, set())
        if not j_s:
            m_s[sid] = 1.0
            continue
        total = sum(
            1.0 if mat_demand.get(j, 0.0) <= 0.0
            else min(1.0, mat_stock.get(j, 0.0) / mat_demand[j])
            for j in j_s
        )
        m_s[sid] = total / len(j_s)

    # ── 10. Матрица стоимостей c_ks (формула 2.35) ────────────────────────
    nK, nS = len(brigade_ids), len(site_ids)
    cost = np.zeros((nK, nS), dtype=float)

    for ki, b_id in enumerate(brigade_ids):
        bq = brigade_quals[b_id]
        for si, s_id in enumerate(site_ids):
            req = site_data[s_id]["required_quals"]
            # h_ks: 0 если хоть одна квалификация совпадает (или требований нет)
            h_ks = 0.0 if (not req or bq & req) else _BIG_M
            # g_ks: нормированное расстояние — данных нет, используем 0
            g_ks = 0.0
            cost[ki, si] = (
                params.alpha1 * h_ks
                + params.alpha2 * g_ks
                + params.alpha3 * (1.0 - m_s[s_id])
            )

    # ── 11. Расширение матрицы на n_max (до n_max бригад на участок) ───────
    # Каждый участок дублируется n_max раз → столбцов nS * n_max
    n_max = params.n_max
    cost_exp = np.tile(cost, n_max)          # shape: nK × (nS * n_max)
    nS_exp = nS * n_max

    # Приводим к квадратной матрице добавлением фиктивных строк/столбцов (стоимость 0)
    size = max(nK, nS_exp)
    cost_sq = np.zeros((size, size), dtype=float)
    cost_sq[:nK, :nS_exp] = cost_exp

    # ── 12. Венгерский алгоритм (формула 2.37) ────────────────────────────
    row_ind, col_ind = linear_sum_assignment(cost_sq)

    # ── 13. Удаление предыдущих назначений для данного расчёта ────────────
    await session.execute(
        sa_delete(BrigadeAssignment).where(
            BrigadeAssignment.schedule_calculation_id == calculation_id
        )
    )

    # ── 14. Сохранение результатов ─────────────────────────────────────────
    objective = 0.0
    new_records: List[BrigadeAssignment] = []

    for ri, ci in zip(row_ind, col_ind):
        # Пропускаем фиктивные строки (бригады) и фиктивные столбцы (участки)
        if ri >= nK or ci >= nS_exp:
            continue

        b_id = brigade_ids[ri]
        si = ci % nS
        s_id = site_ids[si]
        c_ks = float(cost[ri, si])
        objective += c_ks

        period_start = plan_start + timedelta(days=int(site_data[s_id]["min_es"]))
        period_end = plan_start + timedelta(days=int(site_data[s_id]["max_ef"]))

        ba = BrigadeAssignment(
            brigade_id=b_id,
            site_id=s_id,
            period_start=period_start,
            period_end=period_end,
            assignment_cost=round(c_ks, 4),
            schedule_calculation_id=calculation_id,
        )
        session.add(ba)
        new_records.append(ba)

    await session.flush()  # получаем assignment_id до commit

    assignments = [
        AssignmentItem(
            assignment_id=ba.assignment_id,
            brigade_id=ba.brigade_id,
            site_id=ba.site_id,
            period_start=ba.period_start,
            period_end=ba.period_end,
            assignment_cost=float(ba.assignment_cost) if ba.assignment_cost is not None else None,
        )
        for ba in new_records
    ]

    provision_rates = [
        SiteProvisionRate(site_id=sid, m_s=round(m_s[sid], 4))
        for sid in site_ids
    ]

    return BrigadeAssignmentResult(
        calculation_id=calculation_id,
        objective_value=round(objective, 4),
        assignments=assignments,
        provision_rates=provision_rates,
    )
