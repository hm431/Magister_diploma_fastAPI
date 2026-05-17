"""
Расчёт графика поставок материалов.
Формулы 2.8–2.18 подраздела 2.4 (материально-техническое обеспечение).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, NamedTuple, Tuple

import numpy as np
from scipy.optimize import linprog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ScheduleCalculationError
from app.models.mtr import (
    MaterialAvailabilityDate,
    MaterialDemand,
    PlannedDelivery,
)
from app.models.norm import ConsumptionNorm, SupplyContract
from app.models.mtr import StockBalance
from app.models.ref_object import Material
from app.models.sro import ScheduleCalculation, ScheduleItem, Work
from app.schemas.mtr import (
    AvailabilityRow,
    DeliveryRow,
    DemandRow,
    SupplyPlanResponse,
)


# ---------------------------------------------------------------------------
# Вспомогательные структуры
# ---------------------------------------------------------------------------

class _Contract(NamedTuple):
    contract_id: int
    supplier_id: int
    material_id: int
    price: float           # c_{jlt}
    min_days: int          # τ_{jl}^мин
    max_volume: float      # W_{jl}  (None → без ограничения, заменяем ∞)


class _WorkInfo(NamedTuple):
    work_id: int
    work_type_id: int
    volume: float      # v_i
    duration: int      # d_i
    es: int            # ES_i (в днях от нач. проекта)
    ef: int            # EF_i


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------

async def run_supply_plan(
    project_id: int,
    calculation_id: int,
    session: AsyncSession,
) -> SupplyPlanResponse:
    """
    Шаги 1–5 (формулы 2.8–2.18).
    Возвращает заполненный SupplyPlanResponse и сохраняет результат в БД.
    """

    # ── 0. Загрузка расчёта ──────────────────────────────────────────────
    calc = await session.get(ScheduleCalculation, calculation_id)
    if not calc or calc.project_id != project_id:
        raise NotFoundError(message=f"Расчёт {calculation_id} не найден для проекта {project_id}")

    project_start: date = (
        await session.get(
            __import__("app.models.sro", fromlist=["Project"]).Project, project_id
        )
    ).plan_start

    # ── 1. Загрузка schedule_item → _WorkInfo ────────────────────────────
    si_rows = (
        await session.scalars(
            select(ScheduleItem).where(ScheduleItem.calculation_id == calculation_id)
        )
    ).all()

    if not si_rows:
        raise ScheduleCalculationError(message="Нет позиций расписания для данного расчёта")

    work_ids = [si.work_id for si in si_rows]
    works_map: Dict[int, Work] = {
        w.work_id: w
        for w in (
            await session.scalars(select(Work).where(Work.work_id.in_(work_ids)))
        ).all()
    }

    work_infos: List[_WorkInfo] = []
    for si in si_rows:
        w = works_map[si.work_id]
        work_infos.append(
            _WorkInfo(
                work_id=w.work_id,
                work_type_id=w.work_type_id,
                volume=float(w.volume),
                duration=int(w.duration),
                es=int(si.es),
                ef=int(si.ef),
            )
        )

    T = max(wi.ef for wi in work_infos)  # горизонт планирования (дней)
    days = list(range(1, T + 1))         # t = 1..T

    # ── 2. Нормы расхода r_{ij}: work_type → material → value ───────────
    norm_rows = (
        await session.scalars(select(ConsumptionNorm))
    ).all()

    # Берём актуальную норму — последнюю по effective_from
    norms: Dict[Tuple[int, int], float] = {}  # (work_type_id, material_id) → r_ij
    for nr in norm_rows:
        key = (nr.work_type_id, nr.material_id)
        if key not in norms or nr.effective_from > norms.get(("date_" + str(key), 0), date.min):
            norms[key] = float(nr.norm_value)

    # Собираем множество задействованных material_id
    material_ids: set = set()
    for wi in work_infos:
        for (wt, m), _ in norms.items():
            if wt == wi.work_type_id:
                material_ids.add(m)
    material_ids = sorted(material_ids)

    if not material_ids:
        raise ScheduleCalculationError(message="Нет норм расхода материалов для работ проекта")

    # ── Шаг 1: X_{it} (2.8) и Шаг 2: Q_{jt} (2.9) ──────────────────────
    # Q_jt[j][t] — суточная потребность
    Q: Dict[int, Dict[int, float]] = {m: {t: 0.0 for t in days} for m in material_ids}
    for wi in work_infos:
        rate = wi.volume / wi.duration  # v_i / d_i
        for t in days:
            # X_{it} = 1 если ES_i <= t <= EF_i
            if wi.es < t <= wi.ef:  # ES — начало до t, EF >= t (дни с 1-based)
                for mat_id in material_ids:
                    r_ij = norms.get((wi.work_type_id, mat_id), 0.0)
                    if r_ij > 0:
                        Q[mat_id][t] += rate * r_ij

    # ── 3. Начальные остатки S^0_j ───────────────────────────────────────
    sb_rows = (
        await session.scalars(
            select(StockBalance).where(StockBalance.material_id.in_(material_ids))
        )
    ).all()

    # Берём последний остаток по каждому материалу (суммируем по складам)
    S0: Dict[int, float] = defaultdict(float)
    for sb in sb_rows:
        S0[sb.material_id] += float(sb.quantity) - float(sb.reserved_quantity)

    # ── 4. Договоры поставщиков ───────────────────────────────────────────
    contract_rows = (
        await session.scalars(
            select(SupplyContract).where(
                SupplyContract.material_id.in_(material_ids),
                SupplyContract.valid_to.is_(None)
                | (SupplyContract.valid_to >= project_start),
            )
        )
    ).all()

    contracts: List[_Contract] = []
    for c in contract_rows:
        contracts.append(
            _Contract(
                contract_id=c.contract_id,
                supplier_id=c.supplier_id,
                material_id=c.material_id,
                price=float(c.price_per_unit),
                min_days=int(c.min_delivery_days),
                max_volume=float(c.max_volume_per_period) if c.max_volume_per_period else 1e9,
            )
        )

    if not contracts:
        raise ScheduleCalculationError(message="Нет действующих договоров поставки")

    # ── Страховой запас Z_j^мин (формула 2.15) ───────────────────────────────
    mat_rows = (
        await session.scalars(
            select(Material).where(Material.material_id.in_(material_ids))
        )
    ).all()
    Z_min: Dict[int, float] = {
        m.material_id: float(m.safety_stock or 0.0) for m in mat_rows
    }
    # Для материалов без записи в справочнике — 0
    for m_id in material_ids:
        if m_id not in Z_min:
            Z_min[m_id] = 0.0

    # ── Шаг 3: LP (2.13–2.17) ────────────────────────────────────────────
    # Переменные: x_{jlt} — объём поставки материала j по договору l в день t
    # Индексируем: var[(j, l, t)] = idx
    var_index: Dict[Tuple[int, int, int], int] = {}
    idx = 0
    for mat_id in material_ids:
        for ci, c in enumerate(contracts):
            if c.material_id != mat_id:
                continue
            for t in days:
                var_index[(mat_id, ci, t)] = idx
                idx += 1

    n_vars = idx
    if n_vars == 0:
        raise ScheduleCalculationError(message="Нет переменных для LP — проверьте договоры и материалы")

    c_obj = np.zeros(n_vars)
    for (mat_id, ci, t), v_idx in var_index.items():
        c_obj[v_idx] = contracts[ci].price  # c_{jlt}

    # Ограничения неравенства A_ub @ x <= b_ub
    A_ub_rows: List[np.ndarray] = []
    b_ub: List[float] = []

    # (2.14) sum_t(x_jlt) <= W_{jl}
    for mat_id in material_ids:
        for ci, c in enumerate(contracts):
            if c.material_id != mat_id:
                continue
            row = np.zeros(n_vars)
            for t in days:
                k = var_index.get((mat_id, ci, t))
                if k is not None:
                    row[k] = 1.0
            A_ub_rows.append(row)
            b_ub.append(c.max_volume)

    # (2.15) S_jt >= Z_j^мин  →  -sum_{τ<=t}(sum_l x_{jlτ}) <= S^0_j - Z_j^мин - sum_{τ<=t}(Q_{jτ})
    # Развёртывается: -sum_{τ=1}^{t}(sum_l x_{jlτ}) <= S^0_j - Z_j^мин - cumQ_{jt}
    for mat_id in material_ids:
        cum_Q = 0.0
        for t in days:
            cum_Q += Q[mat_id][t]
            row = np.zeros(n_vars)
            for ci, c in enumerate(contracts):
                if c.material_id != mat_id:
                    continue
                for tau in range(1, t + 1):
                    k = var_index.get((mat_id, ci, tau))
                    if k is not None:
                        row[k] = -1.0
            A_ub_rows.append(row)
            b_ub.append(S0[mat_id] - Z_min[mat_id] - cum_Q)

    # (2.11) нет дефицита: S_jt + sum_l(x_jlt) >= Q_jt
    # ⟺ -sum_{τ<=t}(sum_l x_{jlτ}) <= S^0_j - sum_{τ<=t}(Q_{jτ})
    for mat_id in material_ids:
        cum_Q = 0.0
        for t in days:
            cum_Q += Q[mat_id][t]
            row = np.zeros(n_vars)
            for ci, c in enumerate(contracts):
                if c.material_id != mat_id:
                    continue
                for tau in range(1, t + 1):
                    k = var_index.get((mat_id, ci, tau))
                    if k is not None:
                        row[k] = -1.0
            A_ub_rows.append(row)
            b_ub.append(S0[mat_id] - cum_Q)

    A_ub = np.vstack(A_ub_rows) if A_ub_rows else np.empty((0, n_vars))
    b_ub_arr = np.array(b_ub)

    # Границы переменных: x >= 0; x = 0 если t < τ_{jl}^мин (2.16–2.17)
    bounds = []
    for (mat_id, ci, t), v_idx in var_index.items():
        if t < contracts[ci].min_days:
            bounds.append((0.0, 0.0))   # запрет поставки до τ^мин
        else:
            bounds.append((0.0, None))

    result = linprog(
        c=c_obj,
        A_ub=A_ub,
        b_ub=b_ub_arr,
        bounds=bounds,
        method="highs",
    )

    solver_status = result.message

    # ── Шаг 4: Сохранить x_jlt > 0 в mtr.planned_delivery ───────────────
    # Очистить предыдущие плановые поставки для этого проекта
    from sqlalchemy import delete as sa_delete
    await session.execute(
        sa_delete(PlannedDelivery).where(PlannedDelivery.project_id == project_id)
    )

    delivery_rows: List[DeliveryRow] = []
    x_vals = result.x if result.x is not None else np.zeros(n_vars)

    for (mat_id, ci, t), v_idx in var_index.items():
        vol = float(x_vals[v_idx])
        if vol < 1e-6:
            continue
        c = contracts[ci]
        delivery_date = project_start + timedelta(days=t - 1)
        session.add(
            PlannedDelivery(
                project_id=project_id,
                material_id=mat_id,
                warehouse_id=_get_warehouse_for_supplier(c.supplier_id),
                supplier_id=c.supplier_id,
                planned_date=delivery_date,
                planned_volume=round(vol, 3),
                unit_cost=c.price,
                status="planned",
            )
        )
        delivery_rows.append(
            DeliveryRow(
                material_id=mat_id,
                warehouse_id=_get_warehouse_for_supplier(c.supplier_id),
                supplier_id=c.supplier_id,
                planned_date=delivery_date,
                planned_volume=round(vol, 3),
                unit_cost=c.price,
            )
        )

    # Сохранить Q_{jt} в mtr.material_demand
    await session.execute(
        sa_delete(MaterialDemand).where(
            MaterialDemand.project_id == project_id,
            MaterialDemand.schedule_calculation_id == calculation_id,
        )
    )
    demand_rows: List[DemandRow] = []
    for mat_id in material_ids:
        for t in days:
            q = Q[mat_id][t]
            if q < 1e-9:
                continue
            demand_date = project_start + timedelta(days=t - 1)
            session.add(
                MaterialDemand(
                    project_id=project_id,
                    material_id=mat_id,
                    demand_date=demand_date,
                    schedule_calculation_id=calculation_id,
                    quantity=round(q, 3),
                )
            )
            demand_rows.append(DemandRow(material_id=mat_id, demand_date=demand_date, quantity=round(q, 3)))

    # ── Шаг 5: T_доступ(j) (2.18) ────────────────────────────────────────
    # Строим S_{jt} по найденному плану
    S: Dict[int, Dict[int, float]] = {m: {} for m in material_ids}
    for mat_id in material_ids:
        s = S0[mat_id]
        for t in days:
            inflow = sum(
                float(x_vals[var_index[(mat_id, ci, t)]])
                for ci, c in enumerate(contracts)
                if c.material_id == mat_id and (mat_id, ci, t) in var_index
            )
            s = s + inflow - Q[mat_id][t]
            S[mat_id][t] = s

    # T_доступ(j) = min t : S_{jτ} >= Q_{jτ} для всех τ <= t (2.18)
    await session.execute(
        sa_delete(MaterialAvailabilityDate).where(
            MaterialAvailabilityDate.project_id == project_id,
            MaterialAvailabilityDate.calculation_id == calculation_id,
        )
    )
    avail_rows: List[AvailabilityRow] = []
    for mat_id in material_ids:
        avail_t = None
        for t in days:
            if all(S[mat_id][tau] >= Q[mat_id][tau] for tau in range(1, t + 1)):
                avail_t = t
                break
        if avail_t is None:
            avail_t = T  # покрытие не достигнуто — берём последний день
        avail_date = project_start + timedelta(days=avail_t - 1)
        session.add(
            MaterialAvailabilityDate(
                project_id=project_id,
                material_id=mat_id,
                calculation_id=calculation_id,
                availability_date=avail_date,
            )
        )
        avail_rows.append(AvailabilityRow(material_id=mat_id, availability_date=avail_date))

    await session.commit()

    total_cost = float(c_obj @ x_vals)
    return SupplyPlanResponse(
        project_id=project_id,
        calculation_id=calculation_id,
        total_cost=round(total_cost, 2),
        demand=demand_rows,
        deliveries=delivery_rows,
        availability=avail_rows,
        solver_status=solver_status,
    )


def _get_warehouse_for_supplier(supplier_id: int) -> int:
    """
    Заглушка: в реальной схеме warehouse_id привязан к договору или складу.
    Здесь возвращаем 1 — основной склад.
    Расширяется при добавлении warehouse_id в norm.supply_contract.
    """
    return 1
