"""
Динамический пересчёт сроков по фактическим данным.
Задача 4 — формулы 2.51–2.64 подраздела 2.6.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import date
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mtr import (
    ActualDelivery,
    MaterialDemand,
    PlannedDelivery,
    StockBalance,
    StockMovement,
)
from app.models.norm import ConsumptionNorm, SupplyContract
from app.models.ops import (
    CorrectionScenario,
    Deviation,
    DeviationCause,
    WorkProgress,
)
from app.models.risk import SupplierDeliveryStats
from app.models.ref_brigade import Brigade
from app.models.sro import (
    BrigadeAssignment,
    Project,
    ScheduleCalculation,
    ScheduleItem,
    Work,
    WorkPredecessor,
)
from app.schemas.ops import (
    DeviationCauseItem,
    DeviationItem,
    RecalculateRequest,
    RecalculateResponse,
    ScheduleItemActual,
    ScenarioResult,
)

_DEVIATION_THRESHOLD = 0.05   # δ = 0.05 (формула 2.53)


# ---------------------------------------------------------------------------
# Топологическая сортировка (алгоритм Кана)
# ---------------------------------------------------------------------------

def _topo_sort(work_ids: List[int], preds_map: Dict[int, List[int]]) -> List[int]:
    succs: Dict[int, List[int]] = defaultdict(list)
    in_deg: Dict[int, int] = {w: 0 for w in work_ids}
    for wid in work_ids:
        for p in preds_map.get(wid, []):
            succs[p].append(wid)
            in_deg[wid] += 1
    queue: deque[int] = deque(w for w, d in in_deg.items() if d == 0)
    order: List[int] = []
    while queue:
        wid = queue.popleft()
        order.append(wid)
        for s in succs[wid]:
            in_deg[s] -= 1
            if in_deg[s] == 0:
                queue.append(s)
    return order


# ---------------------------------------------------------------------------
# Прямой и обратный проходы сетевой модели (формулы 2.57–2.59)
# ---------------------------------------------------------------------------

def _forward_pass(
    topo_order: List[int],
    preds_map: Dict[int, List[int]],
    work_state: Dict[int, str],          # 'done' | 'active' | 'pending'
    ef_done: Dict[int, int],             # ef для завершённых работ
    es_active: Dict[int, int],           # es для активных работ (= fact_es_day)
    d_ost: Dict[int, int],               # остаточная длительность (active)
    d_plan: Dict[int, int],              # плановая длительность (pending)
    t_0_day: int,
    avail_days: Dict[int, int],          # T_доступ^факт(j) в днях от plan_start
    mat_needs: Dict[int, List[int]],     # work_id -> [material_id]
) -> Tuple[Dict[int, int], Dict[int, int]]:
    es_act: Dict[int, int] = {}
    ef_act: Dict[int, int] = {}

    for wid in topo_order:
        state = work_state.get(wid, "pending")
        pred_ef = max((ef_act[p] for p in preds_map.get(wid, []) if p in ef_act), default=0)

        if state == "done":
            es_act[wid] = pred_ef
            ef_act[wid] = ef_done.get(wid, t_0_day)
        elif state == "active":
            es_act[wid] = es_active[wid]
            ef_act[wid] = t_0_day + d_ost[wid]
        else:
            mat_t = max(
                (avail_days[j] for j in mat_needs.get(wid, []) if j in avail_days),
                default=0,
            )
            es_act[wid] = max(pred_ef, mat_t, t_0_day)
            ef_act[wid] = es_act[wid] + d_plan.get(wid, 0)

    return es_act, ef_act


def _backward_pass(
    topo_order: List[int],
    succs_map: Dict[int, List[int]],
    es_act: Dict[int, int],
    ef_act: Dict[int, int],
    work_state: Dict[int, str],
    d_ost: Dict[int, int],
    d_plan: Dict[int, int],
    t_proj: int,
) -> Tuple[Dict[int, int], Dict[int, int], Dict[int, bool]]:
    lf_act: Dict[int, int] = {}
    ls_act: Dict[int, int] = {}

    for wid in reversed(topo_order):
        succ_ls = [ls_act[s] for s in succs_map.get(wid, []) if s in ls_act]
        lf_act[wid] = min(succ_ls) if succ_ls else t_proj
        state = work_state.get(wid, "pending")
        dur = d_ost.get(wid, 0) if state == "active" else (0 if state == "done" else d_plan.get(wid, 0))
        ls_act[wid] = lf_act[wid] - dur

    is_critical = {wid: abs(lf_act[wid] - ef_act[wid]) < 1 for wid in topo_order}
    return ls_act, lf_act, is_critical


# ---------------------------------------------------------------------------
# T_доступ^факт(j) по формуле 2.18 с фактическими остатками
# ---------------------------------------------------------------------------

def _compute_avail_days(
    material_ids: List[int],
    current_stock: Dict[int, float],
    future_deliveries: Dict[int, List[Tuple[int, float]]],   # j -> [(day, volume)]
    remaining_demand: Dict[int, float],
    t_0_day: int,
) -> Dict[int, int]:
    result: Dict[int, int] = {}
    for j in material_ids:
        stock = current_stock.get(j, 0.0)
        demand = remaining_demand.get(j, 0.0)
        if demand <= 0.0 or stock >= demand:
            result[j] = t_0_day
            continue
        deliveries = sorted(future_deliveries.get(j, []), key=lambda x: x[0])
        cum = stock
        found = False
        for day, vol in deliveries:
            cum += vol
            if cum >= demand:
                result[j] = day
                found = True
                break
        if not found:
            result[j] = (deliveries[-1][0] + 30) if deliveries else (t_0_day + 180)
    return result


# ---------------------------------------------------------------------------
# Основная функция сервиса
# ---------------------------------------------------------------------------

async def recalculate_project(
    project_id: int,
    request: RecalculateRequest,
    session: AsyncSession,
) -> RecalculateResponse:
    t_0: date = request.t_0
    beta1, beta2, beta3 = request.beta1, request.beta2, request.beta3

    # ── Загрузка проекта ──────────────────────────────────────────────────────
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

    plan_start: date = project.plan_start
    plan_finish: date = project.plan_finish
    T_plan: int = (plan_finish - plan_start).days
    t_0_day: int = (t_0 - plan_start).days

    # ── Загрузка работ ────────────────────────────────────────────────────────
    works_res = await session.execute(
        select(Work).where(Work.project_id == project_id)
    )
    works = works_res.scalars().all()
    if not works:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не содержит работ")

    work_ids = [w.work_id for w in works]
    work_by_id = {w.work_id: w for w in works}

    # ── Плановый график (последняя версия сценария 'plan') ────────────────────
    plan_calc_res = await session.execute(
        select(ScheduleCalculation)
        .where(
            ScheduleCalculation.project_id == project_id,
            ScheduleCalculation.scenario == "plan",
        )
        .order_by(ScheduleCalculation.version.desc())
        .limit(1)
    )
    plan_calc = plan_calc_res.scalar_one_or_none()
    if plan_calc is None:
        raise HTTPException(
            status_code=422, detail="Нет планового расчёта для проекта. Сначала выполните CPM."
        )

    items_res = await session.execute(
        select(ScheduleItem).where(ScheduleItem.calculation_id == plan_calc.calculation_id)
    )
    plan_items: Dict[int, ScheduleItem] = {si.work_id: si for si in items_res.scalars().all()}

    # ── Предшественники ───────────────────────────────────────────────────────
    preds_res = await session.execute(
        select(WorkPredecessor).where(WorkPredecessor.work_id.in_(work_ids))
    )
    preds_map: Dict[int, List[int]] = defaultdict(list)
    for p in preds_res.scalars().all():
        preds_map[p.work_id].append(p.predecessor_work_id)

    succs_map: Dict[int, List[int]] = defaultdict(list)
    for wid in work_ids:
        for pred in preds_map.get(wid, []):
            succs_map[pred].append(wid)

    topo_order = _topo_sort(work_ids, preds_map)
    if len(topo_order) != len(work_ids):
        raise HTTPException(status_code=422, detail="Граф работ содержит цикл")

    # ── Нормы расхода r_ij ─────────────────────────────────────────────────────
    work_type_ids = list({w.work_type_id for w in works})
    norms_res = await session.execute(
        select(ConsumptionNorm).where(ConsumptionNorm.work_type_id.in_(work_type_ids))
    )
    # Берём актуальную норму на дату t_0
    latest_norm: Dict[Tuple[int, int], ConsumptionNorm] = {}
    for n in norms_res.scalars().all():
        key = (n.work_type_id, n.material_id)
        if key not in latest_norm or n.effective_from <= t_0 and n.effective_from > latest_norm[key].effective_from:
            latest_norm[key] = n

    # work_id -> list[material_id] (только r_ij > 0)
    mat_needs: Dict[int, List[int]] = defaultdict(list)
    # work_id -> {material_id: r_ij}
    norm_map: Dict[int, Dict[int, float]] = defaultdict(dict)
    for (wt_id, mat_id), n in latest_norm.items():
        for w in works:
            if w.work_type_id == wt_id:
                mat_needs[w.work_id].append(mat_id)
                norm_map[w.work_id][mat_id] = float(n.norm_value)

    material_ids = list({mid for mids in mat_needs.values() for mid in mids})

    # ── Фактический прогресс p_i^факт(t_0) и ES_i^факт ──────────────────────
    progress_res = await session.execute(
        select(WorkProgress).where(
            WorkProgress.work_id.in_(work_ids),
            WorkProgress.report_date == t_0,
        )
    )
    progress_map: Dict[int, WorkProgress] = {
        wp.work_id: wp for wp in progress_res.scalars().all()
    }

    # ── Фактический остаток V_j,t_0^факт ─────────────────────────────────────
    # Последний stock_balance до t_0 + actual_delivery до t_0 + stock_movement до t_0
    if material_ids:
        # Последняя запись остатка по каждому материалу
        subq = (
            select(
                StockBalance.material_id,
                func.max(StockBalance.balance_date).label("max_date"),
            )
            .where(StockBalance.balance_date <= t_0)
            .group_by(StockBalance.material_id)
            .subquery()
        )
        stock_res = await session.execute(
            select(
                StockBalance.material_id,
                func.sum(StockBalance.quantity).label("qty"),
            )
            .join(
                subq,
                and_(
                    StockBalance.material_id == subq.c.material_id,
                    StockBalance.balance_date == subq.c.max_date,
                ),
            )
            .group_by(StockBalance.material_id)
        )
        base_stock: Dict[int, float] = {r.material_id: float(r.qty) for r in stock_res}

        # Фактические поставки после последнего остатка до t_0
        adel_res = await session.execute(
            select(
                ActualDelivery.material_id,
                ActualDelivery.delivery_date,
                ActualDelivery.actual_volume,
                ActualDelivery.supplier_id,
            ).where(
                ActualDelivery.material_id.in_(material_ids),
                ActualDelivery.delivery_date <= t_0,
            )
        )
        actual_deliveries_raw = adel_res.all()

        # Фактический расход (движение) до t_0
        mov_res = await session.execute(
            select(
                StockMovement.material_id,
                func.sum(StockMovement.quantity).label("total"),
            )
            .where(
                StockMovement.material_id.in_(material_ids),
                StockMovement.movement_date <= t_0,
            )
            .group_by(StockMovement.material_id)
        )
        movements: Dict[int, float] = {r.material_id: float(r.total) for r in mov_res}
    else:
        base_stock = {}
        actual_deliveries_raw = []
        movements = {}

    # Суммарный фактический объём поставок до t_0 по материалу
    adel_by_mat: Dict[int, float] = defaultdict(float)
    adel_suppliers: Dict[int, int] = {}   # material_id -> последний поставщик
    for row in actual_deliveries_raw:
        adel_by_mat[row.material_id] += float(row.actual_volume)
        adel_suppliers[row.material_id] = row.supplier_id

    current_stock: Dict[int, float] = {}
    for j in material_ids:
        current_stock[j] = (
            base_stock.get(j, 0.0)
            + adel_by_mat.get(j, 0.0)
            + movements.get(j, 0.0)   # movement: отрицательное = расход
        )

    # ── Плановая потребность по материалам ───────────────────────────────────
    if material_ids:
        demand_res = await session.execute(
            select(
                MaterialDemand.material_id,
                MaterialDemand.demand_date,
                MaterialDemand.quantity,
            ).where(
                MaterialDemand.project_id == project_id,
                MaterialDemand.material_id.in_(material_ids),
            )
        )
        demand_rows = demand_res.all()
    else:
        demand_rows = []

    # Суммарная плановая потребность по материалу до t_0 (для проверки дефицита)
    plan_demand_to_t0: Dict[int, float] = defaultdict(float)
    plan_demand_after_t0: Dict[int, float] = defaultdict(float)
    for row in demand_rows:
        if row.demand_date <= t_0:
            plan_demand_to_t0[row.material_id] += float(row.quantity)
        else:
            plan_demand_after_t0[row.material_id] += float(row.quantity)

    # ── Будущие плановые поставки (не отменённые) для T_доступ^факт ──────────
    if material_ids:
        future_del_res = await session.execute(
            select(
                PlannedDelivery.material_id,
                PlannedDelivery.planned_date,
                PlannedDelivery.planned_volume,
                PlannedDelivery.supplier_id,
                PlannedDelivery.unit_cost,
            ).where(
                PlannedDelivery.project_id == project_id,
                PlannedDelivery.material_id.in_(material_ids),
                PlannedDelivery.planned_date > t_0,
                PlannedDelivery.status != "cancelled",
            )
        )
        future_del_rows = future_del_res.all()
    else:
        future_del_rows = []

    future_deliveries: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
    future_del_cost: Dict[int, float] = defaultdict(float)   # material_id -> unit_cost среднее
    future_del_supplier: Dict[int, int] = {}
    for row in future_del_rows:
        day = (row.planned_date - plan_start).days
        future_deliveries[row.material_id].append((day, float(row.planned_volume)))
        future_del_cost[row.material_id] = float(row.unit_cost)
        future_del_supplier[row.material_id] = row.supplier_id

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 1 — Плановый процент выполнения на t_0 (формула 2.52)
    # ═══════════════════════════════════════════════════════════════════════════
    plan_percent: Dict[int, float] = {}
    for wid in work_ids:
        si = plan_items.get(wid)
        if si is None:
            plan_percent[wid] = 0.0
            continue
        es_i, d_i = si.es, work_by_id[wid].duration
        if d_i <= 0:
            plan_percent[wid] = 1.0 if t_0_day >= es_i else 0.0
        else:
            plan_percent[wid] = max(0.0, min(1.0, (t_0_day - es_i) / d_i))

    fact_percent: Dict[int, float] = {
        wid: float(progress_map[wid].fact_percent) if wid in progress_map else 0.0
        for wid in work_ids
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 2 — Отклонение и классификация χ_i^МТР (формулы 2.51, 2.53)
    # ═══════════════════════════════════════════════════════════════════════════
    delta_p: Dict[int, float] = {
        wid: plan_percent[wid] - fact_percent[wid] for wid in work_ids
    }

    chi_mtr: Dict[int, bool] = {}
    deficit_causes: Dict[int, List[DeviationCauseItem]] = defaultdict(list)

    for wid in work_ids:
        if delta_p[wid] <= _DEVIATION_THRESHOLD:
            chi_mtr[wid] = False
            continue

        has_mtr_cause = False
        si = plan_items.get(wid)
        work_start_date = plan_start + __import__("datetime").timedelta(days=si.es) if si else plan_start

        for j in mat_needs.get(wid, []):
            # Проверка дефицита: фактический приход до t_0 < плановая потребность до t_0
            actual_supply = base_stock.get(j, 0.0) + adel_by_mat.get(j, 0.0)
            plan_needed = plan_demand_to_t0.get(j, 0.0)
            if actual_supply < plan_needed:
                deficit = plan_needed - actual_supply
                supplier_id = adel_suppliers.get(j) or future_del_supplier.get(j)
                deficit_causes[wid].append(
                    DeviationCauseItem(
                        material_id=j,
                        supplier_id=supplier_id,
                        deficit_volume=round(deficit, 3),
                    )
                )
                has_mtr_cause = True

        chi_mtr[wid] = has_mtr_cause

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 3 — Остаточная длительность активных работ (формулы 2.54–2.56)
    # ═══════════════════════════════════════════════════════════════════════════
    work_state: Dict[int, str] = {}
    d_ost: Dict[int, int] = {}
    ef_done: Dict[int, int] = {}
    es_active: Dict[int, int] = {}
    d_plan_map: Dict[int, int] = {w.work_id: w.duration for w in works}

    for wid in work_ids:
        p_fact = fact_percent[wid]
        w = work_by_id[wid]
        si = plan_items.get(wid)
        d_i = w.duration
        v_i = float(w.volume)
        wp = progress_map.get(wid)

        if p_fact >= 1.0:
            work_state[wid] = "done"
            ef_done[wid] = min(si.ef if si else t_0_day, t_0_day)
        elif p_fact > 0.0:
            work_state[wid] = "active"
            # fact_es_day
            if wp and wp.fact_es:
                fact_es_day = (wp.fact_es - plan_start).days
            else:
                fact_es_day = si.es if si else 0
            es_active[wid] = fact_es_day

            elapsed = t_0_day - fact_es_day
            if elapsed > 0 and v_i > 0:
                pi_i = p_fact * v_i / elapsed          # формула 2.54
                rem_v = (1.0 - p_fact) * v_i
                d_rem = rem_v / pi_i if pi_i > 1e-9 else d_i * (1.0 - p_fact)  # формула 2.55
            else:
                d_rem = d_i * (1.0 - p_fact)           # защита от деления на ноль

            d_ost[wid] = max(1, int(round(d_rem)))      # формула 2.56
        else:
            work_state[wid] = "pending"

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 4 — T_доступ^факт(j) по формуле 2.18 с фактическими данными
    # ═══════════════════════════════════════════════════════════════════════════
    # Оставшаяся потребность в j: для незавершённых работ r_ij * v_i
    remaining_demand: Dict[int, float] = defaultdict(float)
    for wid in work_ids:
        if work_state.get(wid) == "done":
            continue
        p_left = 1.0 - fact_percent[wid]
        for j, r_ij in norm_map.get(wid, {}).items():
            remaining_demand[j] += r_ij * float(work_by_id[wid].volume) * p_left

    avail_days = _compute_avail_days(
        material_ids, current_stock, dict(future_deliveries), dict(remaining_demand), t_0_day
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 5 — Пересчёт сетевой модели (формулы 2.57–2.59)
    # ═══════════════════════════════════════════════════════════════════════════
    es_act, ef_act = _forward_pass(
        topo_order, preds_map, work_state,
        ef_done, es_active, d_ost, d_plan_map,
        t_0_day, avail_days, mat_needs,
    )
    T_actual = max(ef_act.values()) if ef_act else T_plan
    delta_T = T_actual - T_plan   # формула 2.60

    ls_act, lf_act, is_critical = _backward_pass(
        topo_order, succs_map, es_act, ef_act,
        work_state, d_ost, d_plan_map, T_actual,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 6 — Декомпозиция отклонения (формулы 2.61–2.62)
    # ═══════════════════════════════════════════════════════════════════════════
    # Контрфактический проход: убираем ограничения по МТР (avail_days = t_0_day для всех j)
    avail_no_mtr = {j: t_0_day for j in material_ids}
    es_cf, ef_cf = _forward_pass(
        topo_order, preds_map, work_state,
        ef_done, es_active, d_ost, d_plan_map,
        t_0_day, avail_no_mtr, mat_needs,
    )
    T_cf = max(ef_cf.values()) if ef_cf else T_plan
    delta_T_mtr = float(T_actual - T_cf)       # формула 2.61
    delta_T_other = float(delta_T) - delta_T_mtr   # формула 2.62

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 7 — Корректирующие сценарии (формулы 2.63–2.64) только при ΔT > 0
    # ═══════════════════════════════════════════════════════════════════════════
    scenarios: List[ScenarioResult] = []

    if delta_T > 0:
        # σ_1: ускорение поставок дефицитных материалов
        # Сдвигаем все будущие поставки для MTR-дефицитных материалов на min_delivery_days/2 назад
        mtr_material_ids = {
            j
            for wid, has in chi_mtr.items()
            if has
            for j in mat_needs.get(wid, [])
        }
        avail_sigma1 = dict(avail_days)
        extra_cost_sigma1 = 0.0
        for j in mtr_material_ids:
            if j in avail_sigma1:
                # Допущение: экспресс-доставка ускоряет на 30% от текущего опоздания
                delay = avail_sigma1[j] - t_0_day
                if delay > 0:
                    avail_sigma1[j] = t_0_day + max(1, int(delay * 0.7))
                # Дополнительная стоимость: 15% от стоимости поставки
                vol = remaining_demand.get(j, 0.0)
                extra_cost_sigma1 += vol * future_del_cost.get(j, 0.0) * 0.15

        _, ef_s1 = _forward_pass(
            topo_order, preds_map, work_state,
            ef_done, es_active, d_ost, d_plan_map,
            t_0_day, avail_sigma1, mat_needs,
        )
        T_s1 = max(ef_s1.values()) if ef_s1 else T_actual
        dt_s1 = float(T_s1 - T_plan)
        dc_s1 = round(extra_cost_sigma1, 2)
        dr_s1 = 0.0
        j_s1 = beta1 * dt_s1 + beta2 * dc_s1 + beta3 * dr_s1

        # σ_2: перераспределение бригад (формулы 2.63–2.64)
        # Логика: бригады с некритических участков переводим на критические.
        # Прирост производительности → сокращение остаточных длительностей.
        # ─────────────────────────────────────────────────────────────────
        # Загружаем назначения бригад для планового расчёта
        ba_res = await session.execute(
            select(BrigadeAssignment).where(
                BrigadeAssignment.schedule_calculation_id == plan_calc.calculation_id
            )
        )
        assignments_s2 = ba_res.scalars().all()

        # Загружаем численность бригад
        brigade_res = await session.execute(select(Brigade))
        brigades_s2: Dict[int, Brigade] = {b.brigade_id: b for b in brigade_res.scalars().all()}

        # Разбиваем участки на критические и некритические
        critical_site_ids = {
            work_by_id[wid].site_id
            for wid in work_ids
            if is_critical.get(wid, False) and work_state.get(wid) != "done"
        }
        noncritical_site_ids = {
            work_by_id[wid].site_id
            for wid in work_ids
            if not is_critical.get(wid, False)
        }

        # Суммарная численность бригад на критических участках
        headcount_critical = sum(
            brigades_s2[a.brigade_id].headcount
            for a in assignments_s2
            if a.site_id in critical_site_ids and a.brigade_id in brigades_s2
        )
        # Бригады, которые можно перевести (на некритических участках)
        transferable = [
            a for a in assignments_s2
            if a.site_id in noncritical_site_ids and a.brigade_id in brigades_s2
        ]
        headcount_extra = sum(
            brigades_s2[a.brigade_id].headcount for a in transferable
        )

        if headcount_critical > 0 and headcount_extra > 0:
            # Ускорение критического пути пропорционально приросту рабочей силы.
            # Консервативно: эффективность переброски — 50% (бригады не идеально взаимозаменяемы).
            efficiency = 0.5
            speedup_ratio = (headcount_extra * efficiency) / (headcount_critical + headcount_extra * efficiency)
            # Суммарная остаточная длительность критических работ
            critical_remaining = sum(
                d_ost.get(wid, d_plan_map.get(wid, 0))
                for wid in work_ids
                if is_critical.get(wid, False) and work_state.get(wid) != "done"
            )
            saved_days = int(critical_remaining * speedup_ratio)
            T_s2 = max(T_plan, T_actual - saved_days)
            # Стоимость переброски: headcount_extra чел. × кол-во рабочих дней на критическом пути × условная ставка
            daily_rate = 2_000.0   # условная ставка: 2000 руб/чел-день (используется единообразно)
            dc_s2 = round(headcount_extra * max(delta_T, 1) * daily_rate, 2)
        else:
            # Нет данных о назначениях или свободных бригад — сценарий недоступен
            T_s2 = T_actual
            dc_s2 = 0.0

        dt_s2 = float(T_s2 - T_plan)
        dr_s2 = 0.05 if headcount_extra > 0 else 0.15   # риск выше без реальных переброски
        j_s2 = beta1 * dt_s2 + beta2 * dc_s2 + beta3 * dr_s2

        # σ_3: параллельное выполнение работ — убираем некритические предшествования
        preds_parallel = {
            wid: [p for p in preds if is_critical.get(p, False) or is_critical.get(wid, False)]
            for wid, preds in preds_map.items()
        }
        succs_p: Dict[int, List[int]] = defaultdict(list)
        for wid in work_ids:
            for p in preds_parallel.get(wid, []):
                succs_p[p].append(wid)
        topo_p = _topo_sort(work_ids, preds_parallel)
        if len(topo_p) == len(work_ids):
            _, ef_s3 = _forward_pass(
                topo_p, preds_parallel, work_state,
                ef_done, es_active, d_ost, d_plan_map,
                t_0_day, avail_days, mat_needs,
            )
            T_s3 = max(ef_s3.values()) if ef_s3 else T_actual
        else:
            T_s3 = T_actual
        dt_s3 = float(T_s3 - T_plan)
        dc_s3 = 0.0
        dr_s3 = 0.05   # небольшое увеличение риска при параллельном выполнении
        j_s3 = beta1 * dt_s3 + beta2 * dc_s3 + beta3 * dr_s3

        raw = [
            ("sigma1", dt_s1, dc_s1, dr_s1, j_s1),
            ("sigma2", dt_s2, dc_s2, dr_s2, j_s2),
            ("sigma3", dt_s3, dc_s3, dr_s3, j_s3),
        ]
        best_type = min(raw, key=lambda x: x[4])[0]

        scenarios = [
            ScenarioResult(
                scenario_type=stype,
                delta_t=round(dt, 2),
                delta_c=round(dc, 2),
                delta_r=round(dr, 4),
                j_score=round(j, 4),
                is_optimal=(stype == best_type),
            )
            for stype, dt, dc, dr, j in raw
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    # Шаг 8 — Сохранение результатов
    # ═══════════════════════════════════════════════════════════════════════════

    # 8a. Создать ScheduleCalculation scenario='actual'
    next_version_res = await session.execute(
        select(func.max(ScheduleCalculation.version)).where(
            ScheduleCalculation.project_id == project_id,
            ScheduleCalculation.scenario == "actual",
        )
    )
    next_ver = (next_version_res.scalar() or 0) + 1

    actual_calc = ScheduleCalculation(
        project_id=project_id,
        version=next_ver,
        scenario="actual",
        t_min=T_actual,
    )
    session.add(actual_calc)
    await session.flush()
    calc_id: int = actual_calc.calculation_id

    # 8b. ScheduleItem для актуализированного графика
    for wid in work_ids:
        session.add(
            ScheduleItem(
                calculation_id=calc_id,
                work_id=wid,
                es=es_act.get(wid, 0),
                ef=ef_act.get(wid, 0),
                ls=ls_act.get(wid, 0),
                lf=lf_act.get(wid, 0),
                tf=max(0, ls_act.get(wid, 0) - es_act.get(wid, 0)),
                is_critical=is_critical.get(wid, False),
            )
        )

    # 8c. Отклонения и причины
    for wid in work_ids:
        dp = delta_p[wid]
        if dp > _DEVIATION_THRESHOLD:
            dev = Deviation(
                work_id=wid,
                calculation_id=calc_id,
                detection_date=t_0,
                plan_percent=round(plan_percent[wid], 4),
                fact_percent=round(fact_percent[wid], 4),
                delta_percent=round(dp, 4),
                chi_mtr=chi_mtr.get(wid, False),
                category="MTR" if chi_mtr.get(wid, False) else "other",
            )
            session.add(dev)
            await session.flush()

            for cause in deficit_causes.get(wid, []):
                session.add(
                    DeviationCause(
                        deviation_id=dev.deviation_id,
                        material_id=cause.material_id,
                        supplier_id=cause.supplier_id,
                        deficit_volume=cause.deficit_volume,
                    )
                )

    # 8d. Сценарии
    for sc in scenarios:
        session.add(
            CorrectionScenario(
                project_id=project_id,
                calculation_id=calc_id,
                detection_date=t_0,
                scenario_type=sc.scenario_type,
                delta_t=sc.delta_t,
                delta_c=sc.delta_c,
                delta_r=sc.delta_r,
                j_score=sc.j_score,
                is_optimal=sc.is_optimal,
            )
        )

    # 8e. Обновить SupplierDeliveryStats для поставщиков с МТР-дефицитом (формулы 2.43–2.44)
    # Пересчёт μ_jk, σ²_jk на основе фактических данных.
    # planned_tau берём из действующего договора поставки (SupplyContract.min_delivery_days).
    import math as _math

    # Загружаем контракты один раз для всех пар (supplier_id, material_id) из cause-списков
    deficit_pairs = {
        (cause.supplier_id, cause.material_id)
        for cause_list in deficit_causes.values()
        for cause in cause_list
        if cause.supplier_id is not None
    }
    planned_tau_map: Dict[Tuple[int, int], int] = {}
    if deficit_pairs:
        supplier_ids_for_tau = {p[0] for p in deficit_pairs}
        material_ids_for_tau = {p[1] for p in deficit_pairs}
        contracts_for_tau = (await session.scalars(
            select(SupplyContract).where(
                SupplyContract.supplier_id.in_(supplier_ids_for_tau),
                SupplyContract.material_id.in_(material_ids_for_tau),
                SupplyContract.valid_to.is_(None) | (SupplyContract.valid_to >= t_0),
            )
        )).all()
        for c in contracts_for_tau:
            key = (c.supplier_id, c.material_id)
            if key in deficit_pairs:
                planned_tau_map[key] = int(c.min_delivery_days)

    for cause_list in deficit_causes.values():
        for cause in cause_list:
            if cause.supplier_id is None:
                continue
            stats = await session.get(
                SupplierDeliveryStats,
                {"supplier_id": cause.supplier_id, "material_id": cause.material_id},
            )
            if stats is None:
                continue
            # Плановый срок τ_{jk}^план из договора (формула 2.43)
            planned_tau = float(
                planned_tau_map.get((cause.supplier_id, cause.material_id), 1)
            )
            # Фактический срок = плановый + задержка по МТР (формулы 2.43–2.44)
            fact_tau = planned_tau + max(delta_T_mtr, 0.0)
            log_tau = _math.log(max(fact_tau, 0.01))

            # Инкрементальное обновление μ_jk, σ_jk (скользящее среднее/дисперсия)
            n_old = stats.sample_size
            if n_old >= 1:
                mu_new = (stats.mu_jk * n_old + log_tau) / (n_old + 1)
                sigma_new = (
                    _math.sqrt(
                        (stats.sigma_jk ** 2 * (n_old - 1) + (log_tau - mu_new) ** 2)
                        / max(n_old, 1)
                    )
                    if n_old > 1
                    else stats.sigma_jk
                )
                stats.mu_jk = mu_new
                stats.sigma_jk = max(sigma_new, 0.01)
                stats.sample_size = n_old + 1

    await session.commit()

    # ── Формирование ответа ───────────────────────────────────────────────────
    deviation_items = [
        DeviationItem(
            work_id=wid,
            plan_percent=round(plan_percent[wid], 4),
            fact_percent=round(fact_percent[wid], 4),
            delta_percent=round(delta_p[wid], 4),
            chi_mtr=chi_mtr.get(wid, False),
            category="MTR" if chi_mtr.get(wid, False) else "other",
            causes=deficit_causes.get(wid, []),
        )
        for wid in work_ids
        if delta_p[wid] > _DEVIATION_THRESHOLD
    ]

    schedule_items = [
        ScheduleItemActual(
            work_id=wid,
            es=es_act.get(wid, 0),
            ef=ef_act.get(wid, 0),
            ls=ls_act.get(wid, 0),
            lf=lf_act.get(wid, 0),
            tf=max(0, ls_act.get(wid, 0) - es_act.get(wid, 0)),
            is_critical=is_critical.get(wid, False),
        )
        for wid in work_ids
    ]

    return RecalculateResponse(
        project_id=project_id,
        calculation_id=calc_id,
        t_plan=T_plan,
        t_actual=float(T_actual),
        delta_t=float(delta_T),
        delta_t_mtr=round(delta_T_mtr, 2),
        delta_t_other=round(delta_T_other, 2),
        deviations=deviation_items,
        schedule=schedule_items,
        scenarios=scenarios,
    )
