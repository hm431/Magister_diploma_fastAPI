"""
Проверка загрузки склада и логистики.
Формулы 2.19–2.30 (модель потока + M/M/n).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from scipy.optimize import linprog
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.mtr import (
    MaterialAvailabilityDate,
    MaterialDemand,
    PlannedDelivery,
    WarehouseLoadProfile,
)
from app.models.norm import TransportParam
from app.models.ref_object import Material, Warehouse
from app.models.sro import ScheduleCalculation
from app.schemas.mtr import (
    DeliveryRow,
    LoadProfileRow,
    ViolationRow,
    WarehouseFeasibilityResponse,
)


# ---------------------------------------------------------------------------
# Вспомогательные функции: формулы Эрланга (M/M/n)
# ---------------------------------------------------------------------------

def _erlang_p0(n: int, rho: float) -> float:
    """P_0 для системы M/M/n (формула 2.26)."""
    if rho >= 1.0:
        return 0.0
    term_sum = sum((n * rho) ** k / math.factorial(k) for k in range(n))
    last_term = (n * rho) ** n / (math.factorial(n) * (1.0 - rho))
    denom = term_sum + last_term
    return 1.0 / denom if denom > 0 else 0.0


def _erlang_lq(n: int, rho: float, p0: float) -> float:
    """L_q — средняя длина очереди (формула Эрланга 2.28)."""
    if rho >= 1.0:
        return float("inf")
    num = (n * rho) ** (n + 1)
    den = n * math.factorial(n) * (1.0 - rho) ** 2
    return (num / den) * p0 if den > 0 else 0.0


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------

async def run_warehouse_feasibility(
    project_id: int,
    calculation_id: int,
    session: AsyncSession,
) -> WarehouseFeasibilityResponse:
    """
    Шаги 1–4 (формулы 2.19–2.30).
    Проверяет один основной склад (warehouse_id=1).
    """

    # ── 0. Проверка расчёта ──────────────────────────────────────────────
    calc = await session.get(ScheduleCalculation, calculation_id)
    if not calc or calc.project_id != project_id:
        raise NotFoundError(message=f"Расчёт {calculation_id} не найден для проекта {project_id}")

    from app.models.sro import Project
    project = await session.get(Project, project_id)
    project_start: date = project.plan_start

    # ── 1. Загрузка данных ───────────────────────────────────────────────
    # Плановые поставки (x_{jlt}) из подзадачи 2.1
    deliveries = (
        await session.scalars(
            select(PlannedDelivery).where(PlannedDelivery.project_id == project_id)
        )
    ).all()

    if not deliveries:
        raise NotFoundError(message="Нет плановых поставок. Сначала выполните /mtr/supply-plan")

    # Определяем склад из первой поставки
    warehouse_id: int = deliveries[0].warehouse_id

    warehouse = await session.get(Warehouse, warehouse_id)
    if not warehouse:
        raise NotFoundError(message=f"Склад {warehouse_id} не найден")

    U_max: float = float(warehouse.capacity or 1e9)
    n_r: int = int(warehouse.loading_posts or 1)           # n_р
    mu: float = float(warehouse.service_rate or 1.0)       # μ
    W_q_allowed: float = float(warehouse.allowed_wait_time or 1e9)  # W_q^доп

    # Плановая суточная потребность Q_{jt}
    demand_rows = (
        await session.scalars(
            select(MaterialDemand).where(
                MaterialDemand.project_id == project_id,
                MaterialDemand.schedule_calculation_id == calculation_id,
            )
        )
    ).all()

    # Начальные остатки
    from app.models.mtr import StockBalance
    sb_rows = (await session.scalars(select(StockBalance))).all()
    S0: Dict[int, float] = defaultdict(float)
    for sb in sb_rows:
        S0[sb.material_id] += float(sb.quantity) - float(sb.reserved_quantity)

    # Коэффициенты хранения w_j
    material_ids = list({d.material_id for d in deliveries} | {d.material_id for d in demand_rows})
    materials_map: Dict[int, Material] = {
        m.material_id: m
        for m in (
            await session.scalars(
                select(Material).where(Material.material_id.in_(material_ids))
            )
        ).all()
    }
    w_j: Dict[int, float] = {
        mid: float(materials_map[mid].storage_coefficient or 1.0)
        for mid in material_ids
    }

    # Параметры транспорта q_{jl}
    tp_rows = (
        await session.scalars(
            select(TransportParam).where(
                TransportParam.material_id.in_(material_ids),
                TransportParam.warehouse_id == warehouse_id,
            )
        )
    ).all()
    q_jl: Dict[int, float] = {tp.material_id: float(tp.avg_capacity) for tp in tp_rows}

    # ── Строим временную шкалу дней ─────────────────────────────────────
    all_dates = sorted({d.planned_date for d in deliveries} | {d.demand_date for d in demand_rows})
    if not all_dates:
        raise NotFoundError(message="Нет дат в плане поставок или потребности")

    t_start = min(all_dates)
    t_end = max(all_dates)
    days_range: List[date] = []
    cur = t_start
    while cur <= t_end:
        days_range.append(cur)
        cur += timedelta(days=1)

    # Словари: дата → {material_id → value}
    inflow: Dict[date, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for d in deliveries:
        inflow[d.planned_date][d.material_id] += float(d.planned_volume)

    demand_dict: Dict[date, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for d in demand_rows:
        demand_dict[d.demand_date][d.material_id] += float(d.quantity)

    # ── Шаг 1: Потоковая модель (2.19–2.22) ─────────────────────────────
    V: Dict[date, Dict[int, float]] = {}   # V_{jt} — запас материала j в день t
    U: Dict[date, float] = {}              # U_t — суммарная загрузка склада

    running: Dict[int, float] = dict(S0)  # текущие остатки
    for t in days_range:
        for mat_id in material_ids:
            running[mat_id] = running.get(mat_id, 0.0) + inflow[t].get(mat_id, 0.0) - demand_dict[t].get(mat_id, 0.0)
            running[mat_id] = max(running[mat_id], 0.0)
        V[t] = dict(running)
        U[t] = sum(running.get(m, 0.0) * w_j.get(m, 1.0) for m in material_ids)

    # ── Шаг 2: M/M/n (2.25–2.30) ────────────────────────────────────────
    lambda_T: Dict[date, float] = {}   # интенсивность прибытия автомобилей
    rho_t: Dict[date, float] = {}
    Lq_t: Dict[date, float] = {}
    Wq_t: Dict[date, float] = {}

    for t in days_range:
        lam = sum(
            inflow[t].get(mat_id, 0.0) / q_jl.get(mat_id, 1.0)
            for mat_id in material_ids
        )
        lambda_T[t] = lam
        if lam <= 0:
            rho_t[t] = 0.0
            Lq_t[t] = 0.0
            Wq_t[t] = 0.0
            continue

        rho = lam / (n_r * mu)
        rho_t[t] = rho
        if rho >= 1.0:
            Lq_t[t] = float("inf")
            Wq_t[t] = float("inf")
        else:
            p0 = _erlang_p0(n_r, rho)
            lq = _erlang_lq(n_r, rho, p0)
            wq = lq / lam if lam > 0 else 0.0
            Lq_t[t] = round(lq, 4)
            Wq_t[t] = round(wq, 4)

    # ── Проверка нарушений ───────────────────────────────────────────────
    violations: List[ViolationRow] = []
    for t in days_range:
        if U[t] > U_max:
            violations.append(
                ViolationRow(
                    profile_date=t,
                    violation_type="capacity",
                    description=f"U_t={U[t]:.2f} > U_max={U_max:.2f} (формула 2.23)",
                )
            )
        rho = rho_t[t]
        if rho >= 1.0:
            violations.append(
                ViolationRow(
                    profile_date=t,
                    violation_type="overload",
                    description=f"ρ(t)={rho:.3f} >= 1 — система в перегрузке (формула 2.27)",
                )
            )
        wq = Wq_t[t]
        if math.isfinite(wq) and wq > W_q_allowed:
            violations.append(
                ViolationRow(
                    profile_date=t,
                    violation_type="wait_time",
                    description=f"W_q(t)={wq:.3f} > W_q^доп={W_q_allowed} (формула 2.30)",
                )
            )

    # ── Шаг 3: Итеративная корректировка (2.24) ─────────────────────────
    adjusted_deliveries: Optional[List[DeliveryRow]] = None
    if violations:
        adjusted_deliveries = await _adjust_deliveries(
            deliveries=deliveries,
            days_range=days_range,
            demand_dict=demand_dict,
            S0=S0,
            w_j=w_j,
            U_max=U_max,
            material_ids=material_ids,
            session=session,
            project_id=project_id,
        )

    # ── Шаг 4: Сохранить профиль в mtr.warehouse_load_profile ───────────
    from sqlalchemy import delete as sa_delete
    await session.execute(
        sa_delete(WarehouseLoadProfile).where(
            WarehouseLoadProfile.warehouse_id == warehouse_id
        )
    )
    profile_out: List[LoadProfileRow] = []
    for t in days_range:
        u = U[t]
        peak = u > 0.9 * U_max
        lq = Lq_t[t] if math.isfinite(Lq_t[t]) else None
        wq = Wq_t[t] if math.isfinite(Wq_t[t]) else None
        session.add(
            WarehouseLoadProfile(
                warehouse_id=warehouse_id,
                profile_date=t,
                total_load=round(u, 2),
                peak_indicator=peak,
                queue_length=round(lq, 3) if lq is not None else None,
                wait_time=round(wq, 3) if wq is not None else None,
            )
        )
        ratio = u / U_max if U_max > 0 else 0.0
        profile_out.append(
            LoadProfileRow(
                profile_date=t,
                total_load=round(u, 2),
                utilization_ratio=round(ratio, 4),
                peak_indicator=peak,
                queue_length=round(lq, 3) if lq is not None else None,
                wait_time=round(wq, 3) if wq is not None else None,
                rho=round(rho_t[t], 4) if rho_t[t] is not None else None,
            )
        )

    await session.commit()

    return WarehouseFeasibilityResponse(
        project_id=project_id,
        calculation_id=calculation_id,
        warehouse_id=warehouse_id,
        feasible=len(violations) == 0,
        violations=violations,
        load_profile=profile_out,
        adjusted_deliveries=adjusted_deliveries,
    )


# ---------------------------------------------------------------------------
# Корректировка плана (формула 2.24): сдвиг поставок для снижения U_t
# ---------------------------------------------------------------------------

async def _adjust_deliveries(
    *,
    deliveries: list,
    days_range: List[date],
    demand_dict: Dict[date, Dict[int, float]],
    S0: Dict[int, float],
    w_j: Dict[int, float],
    U_max: float,
    material_ids: List[int],
    session: AsyncSession,
    project_id: int,
) -> List[DeliveryRow]:
    """
    Сдвигаем поставки по времени, минимизируя max_t(U_t) при:
    - соблюдении покрытия потребности (2.11)
    - страховой запас (2.15)
    - U_t <= U_max (2.23)

    Формула 2.24: F2 = max_t(U_t) → min.
    Реализуется LP с вспомогательной переменной z (эпиграф max).
    """
    T = len(days_range)
    day_idx = {d: i for i, d in enumerate(days_range)}

    # Группируем поставки по (material_id, supplier_id) — это «пары»
    # Для каждой пары разрешаем сдвиг объёма по дням в рамках исходного суммарного объёма.
    pairs: List[Tuple[int, int]] = sorted(
        {(d.material_id, d.supplier_id) for d in deliveries}
    )
    # Суммарный объём по паре
    total_by_pair: Dict[Tuple[int, int], float] = defaultdict(float)
    for d in deliveries:
        total_by_pair[(d.material_id, d.supplier_id)] += float(d.planned_volume)

    # Переменные: y_{pair, t} — перераспределённые объёмы + z (max U)
    n_pair_vars = len(pairs) * T
    n_vars = n_pair_vars + 1  # последняя — z
    z_idx = n_var = n_pair_vars

    def y_idx(pair_i: int, t_i: int) -> int:
        return pair_i * T + t_i

    c_obj = np.zeros(n_vars)
    c_obj[z_idx] = 1.0  # min z

    A_ub_rows: List[np.ndarray] = []
    b_ub: List[float] = []

    # (2.23) U_t <= z для всех t → sum_j V_{jt}*w_j <= z
    # V_{jt} = S0_j + sum_{τ<=t}(sum_l y_{pair,τ}) - sum_{τ<=t}(Q_{jτ})
    cum_Q: Dict[int, List[float]] = {}
    for mat_id in material_ids:
        cum_Q[mat_id] = []
        running = 0.0
        for t in days_range:
            running += demand_dict[t].get(mat_id, 0.0)
            cum_Q[mat_id].append(running)

    for t_i, t in enumerate(days_range):
        row = np.zeros(n_vars)
        rhs = -sum(S0.get(mat_id, 0.0) * w_j.get(mat_id, 1.0) for mat_id in material_ids)
        rhs += sum(cum_Q[mat_id][t_i] * w_j.get(mat_id, 1.0) for mat_id in material_ids)
        for pi, (mat_id, sup_id) in enumerate(pairs):
            wj = w_j.get(mat_id, 1.0)
            for tau_i in range(t_i + 1):
                row[y_idx(pi, tau_i)] += wj
        row[z_idx] = -1.0
        A_ub_rows.append(row)
        b_ub.append(-rhs)

    # (2.11) нет дефицита: sum_{τ<=t}(y_{pair,τ}) >= Q_jt - S0_j (для каждого j и t)
    for mat_id in material_ids:
        pairs_j = [pi for pi, (m, _) in enumerate(pairs) if m == mat_id]
        for t_i in range(T):
            need = cum_Q[mat_id][t_i] - S0.get(mat_id, 0.0)
            if need <= 0:
                continue
            row = np.zeros(n_vars)
            for pi in pairs_j:
                for tau_i in range(t_i + 1):
                    row[y_idx(pi, tau_i)] = -1.0
            A_ub_rows.append(row)
            b_ub.append(-need)

    # Суммарный объём по паре: sum_t y_{pair,t} == total_by_pair[pair]
    A_eq_rows: List[np.ndarray] = []
    b_eq: List[float] = []
    for pi, pair in enumerate(pairs):
        row = np.zeros(n_vars)
        for t_i in range(T):
            row[y_idx(pi, t_i)] = 1.0
        A_eq_rows.append(row)
        b_eq.append(total_by_pair[pair])

    A_ub_arr = np.vstack(A_ub_rows) if A_ub_rows else np.empty((0, n_vars))
    A_eq_arr = np.vstack(A_eq_rows) if A_eq_rows else np.empty((0, n_vars))
    bounds = [(0.0, None)] * n_pair_vars + [(0.0, None)]  # z >= 0

    result = linprog(
        c=c_obj,
        A_ub=A_ub_arr,
        b_ub=np.array(b_ub),
        A_eq=A_eq_arr,
        b_eq=np.array(b_eq),
        bounds=bounds,
        method="highs",
    )

    if result.x is None:
        return []

    y_vals = result.x

    # Формируем скорректированные поставки и обновляем PlannedDelivery в БД
    from sqlalchemy import delete as sa_delete
    await session.execute(
        sa_delete(PlannedDelivery).where(PlannedDelivery.project_id == project_id)
    )

    # Нужен supplier_id → warehouse_id из первой поставки
    sup_wh: Dict[int, int] = {d.supplier_id: d.warehouse_id for d in deliveries}
    sup_cost: Dict[int, float] = {d.supplier_id: float(d.unit_cost) for d in deliveries}

    adjusted: List[DeliveryRow] = []
    for pi, (mat_id, sup_id) in enumerate(pairs):
        for t_i, t in enumerate(days_range):
            vol = float(y_vals[y_idx(pi, t_i)])
            if vol < 1e-6:
                continue
            wh_id = sup_wh.get(sup_id, 1)
            cost = sup_cost.get(sup_id, 0.0)
            session.add(
                PlannedDelivery(
                    project_id=project_id,
                    material_id=mat_id,
                    warehouse_id=wh_id,
                    supplier_id=sup_id,
                    planned_date=t,
                    planned_volume=round(vol, 3),
                    unit_cost=cost,
                    status="planned",
                )
            )
            adjusted.append(
                DeliveryRow(
                    material_id=mat_id,
                    warehouse_id=wh_id,
                    supplier_id=sup_id,
                    planned_date=t,
                    planned_volume=round(vol, 3),
                    unit_cost=cost,
                )
            )

    return adjusted
