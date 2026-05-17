"""
Имитационная модель оценки рисков срыва сроков (метод Монте-Карло).
Формулы 2.39–2.50 подраздела 2.5 (анализ рисков).
"""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import beta as beta_dist, lognorm
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mtr import StockBalance
from app.models.norm import ConsumptionNorm, SupplyContract
from app.models.risk import (
    MonteCarloIteration,
    MonteCarloRun,
    RiskQuantile,
    SupplierDeliveryStats,
    WorkCriticalityIndex,
    WorkRiskParams,
)
from app.models.sro import Work, WorkPredecessor
from app.schemas.risk import CDFPoint, CriticalWorkItem, MonteCarloRequest, MonteCarloResponse


# ---------------------------------------------------------------------------
# Вспомогательные функции — на уровне модуля (picklable для ProcessPoolExecutor)
# ---------------------------------------------------------------------------

def _compute_beta_params(a: float, m: float, b: float) -> Tuple[float, float, float, float]:
    """
    Вычисляет параметры Beta-распределения методом моментов (формулы 2.39–2.41).
    Возвращает (expected, std, alpha, beta).
    """
    expected = (a + 4.0 * m + b) / 6.0          # формула 2.39
    span = b - a
    if span < 1e-9:
        return expected, 0.0, 1.0, 1.0
    std = span / 6.0                              # формула 2.40
    mu_std = (expected - a) / span               # стандартизованное среднее ∈ (0,1)
    sigma_std2 = (1.0 / 6.0) ** 2               # стандартизованная дисперсия
    k = mu_std * (1.0 - mu_std) / sigma_std2 - 1.0
    k = max(k, 1.0)
    alpha = k * mu_std
    beta_ = k * (1.0 - mu_std)
    return expected, std, max(alpha, 0.01), max(beta_, 0.01)


def _topological_sort(work_list: List[Dict[str, Any]]) -> List[int]:
    """Кан (BFS) топологическая сортировка по predecessors — O(V+E)."""
    successors: Dict[int, List[int]] = defaultdict(list)
    in_degree: Dict[int, int] = {w["work_id"]: 0 for w in work_list}
    for w in work_list:
        for p in w["predecessors"]:
            successors[p].append(w["work_id"])
            in_degree[w["work_id"]] += 1

    queue: deque[int] = deque(wid for wid, deg in in_degree.items() if deg == 0)
    order: List[int] = []
    while queue:
        wid = queue.popleft()
        order.append(wid)
        for s in successors.get(wid, []):
            in_degree[s] -= 1
            if in_degree[s] == 0:
                queue.append(s)
    return order


def _simulate_chunk(
    params: Dict[str, Any],
    seed_base: int,
    chunk_size: int,
) -> List[Tuple[float, List[int]]]:
    """
    Выполняет chunk_size итераций Монте-Карло.
    Возвращает список (T^(r), [work_id критического пути]).
    Определена на уровне модуля для корректной сериализации в ProcessPoolExecutor.
    """
    rng = np.random.default_rng(seed_base)

    works: List[Dict] = params["works"]
    materials: Dict[int, Dict] = params["materials"]
    topo_order: List[int] = params["topo_order"]

    work_by_id: Dict[int, Dict] = {w["work_id"]: w for w in works}
    wid_to_idx: Dict[int, int] = {w["work_id"]: i for i, w in enumerate(works)}
    n_works = len(works)

    # Список преемников для обратного прохода CPM
    successors: Dict[int, List[int]] = defaultdict(list)
    for w in works:
        for p in w["predecessors"]:
            successors[p].append(w["work_id"])

    # Векторизованная выборка Beta для всех работ (chunk_size × n_works) — формула 2.39–2.41
    alphas = np.array([w["alpha"] for w in works], dtype=float)
    betas_ = np.array([w["beta_"] for w in works], dtype=float)
    locs = np.array([w["a"] for w in works], dtype=float)
    scales = np.array([max(w["b"] - w["a"], 1e-9) for w in works], dtype=float)
    d_matrix = rng.beta(alphas, betas_, size=(chunk_size, n_works)) * scales + locs
    d_matrix = np.maximum(d_matrix, 0.0)

    # Векторизованная выборка LogNormal для сроков поставок (формулы 2.42–2.44)
    mat_ids = list(materials.keys())
    n_mats = len(mat_ids)
    mat_idx: Dict[int, int] = {mid: i for i, mid in enumerate(mat_ids)}
    tau_matrix = np.zeros((chunk_size, n_mats), dtype=float)

    for i, mid in enumerate(mat_ids):
        mat = materials[mid]
        if not mat["suppliers"] or mat["initial_stock"] >= mat["total_demand"]:
            continue  # материал покрыт складом → T_доступ = 0
        min_tau = np.full(chunk_size, np.inf)
        for sup in mat["suppliers"]:
            if sup["sample_size"] < 5:
                # fallback — плановый срок с малым шумом (формула 2.43)
                pt = float(sup["planned_tau"])
                noise = rng.normal(0.0, max(pt * 0.05, 0.5), size=chunk_size)
                t_sup = np.maximum(pt + noise, 0.0)
            else:
                # LogNormal(μ_jk, σ_jk) — формула 2.44
                t_sup = lognorm.rvs(
                    s=sup["sigma"],
                    scale=np.exp(sup["mu"]),
                    size=chunk_size,
                    random_state=rng,
                )
                t_sup = np.maximum(t_sup, 0.0)
            min_tau = np.minimum(min_tau, t_sup)
        tau_matrix[:, i] = np.where(np.isinf(min_tau), 0.0, min_tau)

    results: List[Tuple[float, List[int]]] = []

    for r in range(chunk_size):
        d_r = d_matrix[r]           # продолжительности работ в итерации r
        tau_r = tau_matrix[r]       # сроки доступности материалов в итерации r

        # Прямой проход CPM с ресурсным ограничением (формулы 2.1–2.2, 2.6)
        es: Dict[int, float] = {}
        ef: Dict[int, float] = {}

        for wid in topo_order:
            w = work_by_id[wid]
            pred_ef = max((ef[p] for p in w["predecessors"] if p in ef), default=0.0)
            mat_t = max(
                (tau_r[mat_idx[m["material_id"]]] for m in w["materials"] if m["norm_value"] > 0),
                default=0.0,
            )
            es[wid] = max(pred_ef, mat_t)                      # формула 2.6
            ef[wid] = es[wid] + d_r[wid_to_idx[wid]]          # формула 2.2

        t_result = max(ef.values()) if ef else 0.0             # формула 2.45

        # Обратный проход CPM — вычисление TF для определения критического пути
        lf: Dict[int, float] = {}
        ls: Dict[int, float] = {}

        for wid in reversed(topo_order):
            succ_ls = [ls[s] for s in successors.get(wid, []) if s in ls]
            lf[wid] = min(succ_ls) if succ_ls else t_result
            ls[wid] = lf[wid] - d_r[wid_to_idx[wid]]

        # Критический путь C^(r): работы с TF = LF - EF ≈ 0
        critical = [
            wid for wid in topo_order
            if abs(lf.get(wid, 0.0) - ef.get(wid, 0.0)) < 1e-6
        ]
        results.append((t_result, critical))

    return results


# ---------------------------------------------------------------------------
# Основная async-функция сервиса
# ---------------------------------------------------------------------------

async def run_monte_carlo(
    project_id: int,
    request: MonteCarloRequest,
    session: AsyncSession,
) -> MonteCarloResponse:
    """
    Полный пайплайн имитационной оценки рисков (формулы 2.39–2.50).
    """
    iterations = request.iterations
    seed = request.seed
    t_plan = request.t_plan

    # ── Шаг 1: Загрузка работ проекта ────────────────────────────────────────
    works_res = await session.execute(
        select(Work).where(Work.project_id == project_id)
    )
    works = works_res.scalars().all()
    if not works:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден или не содержит работ")

    work_ids = [w.work_id for w in works]
    work_type_ids = list({w.work_type_id for w in works})

    preds_res = await session.execute(
        select(WorkPredecessor).where(WorkPredecessor.work_id.in_(work_ids))
    )
    preds = preds_res.scalars().all()
    predecessors_map: Dict[int, List[int]] = defaultdict(list)
    for p in preds:
        predecessors_map[p.work_id].append(p.predecessor_work_id)

    # ── Шаг 1 (продолж.): Параметры PERT — загрузка и дополнение ─────────────
    rp_res = await session.execute(
        select(WorkRiskParams).where(WorkRiskParams.work_id.in_(work_ids))
    )
    risk_params: Dict[int, WorkRiskParams] = {rp.work_id: rp for rp in rp_res.scalars().all()}

    # Для записей без вычисленных alpha/beta — рассчитать и сохранить (формулы 2.39–2.41)
    for rp in list(risk_params.values()):
        if rp.alpha is None or rp.beta_param is None:
            exp, std, alpha, beta_ = _compute_beta_params(rp.a_i, rp.m_i, rp.b_i)
            rp.alpha = alpha
            rp.beta_param = beta_
            rp.expected_duration = exp
            rp.std_deviation = std
    await session.flush()

    # ── Загрузка норм расхода материалов ─────────────────────────────────────
    norms_res = await session.execute(
        select(ConsumptionNorm).where(ConsumptionNorm.work_type_id.in_(work_type_ids))
    )
    norms_all = norms_res.scalars().all()

    # Берём последнюю норму по (work_type_id, material_id)
    latest_norm: Dict[Tuple[int, int], ConsumptionNorm] = {}
    for n in norms_all:
        key = (n.work_type_id, n.material_id)
        if key not in latest_norm or n.effective_from > latest_norm[key].effective_from:
            latest_norm[key] = n

    norm_map: Dict[int, List[Dict]] = defaultdict(list)
    for (wt_id, mat_id), n in latest_norm.items():
        norm_map[wt_id].append({"material_id": mat_id, "norm_value": float(n.norm_value)})

    material_ids = list({n.material_id for n in norms_all})

    # ── Шаг 2: Параметры логнормального τ_jk (формулы 2.42–2.44) ─────────────
    if material_ids:
        stats_res = await session.execute(
            select(SupplierDeliveryStats).where(
                SupplierDeliveryStats.material_id.in_(material_ids)
            )
        )
        stats_map: Dict[Tuple[int, int], SupplierDeliveryStats] = {
            (s.supplier_id, s.material_id): s for s in stats_res.scalars().all()
        }

        contracts_res = await session.execute(
            select(SupplyContract).where(SupplyContract.material_id.in_(material_ids))
        )
        contracts = contracts_res.scalars().all()
    else:
        stats_map = {}
        contracts = []

    mat_suppliers: Dict[int, List[Dict]] = defaultdict(list)
    for c in contracts:
        key = (c.supplier_id, c.material_id)
        stat = stats_map.get(key)
        if stat:
            mu = float(stat.mu_jk)
            sigma = float(stat.sigma_jk)
            sample_size = stat.sample_size
        else:
            # Fallback — детерминированный плановый срок с малой σ (формула 2.43)
            planned = float(c.min_delivery_days)
            mu = float(np.log(max(planned, 1.0)))
            sigma = 0.1
            sample_size = 0
        mat_suppliers[c.material_id].append({
            "supplier_id": c.supplier_id,
            "mu": mu,
            "sigma": sigma,
            "planned_tau": float(c.min_delivery_days),
            "sample_size": sample_size,
        })

    # Начальные остатки на складах S^0_j
    stock_map: Dict[int, float] = defaultdict(float)
    if material_ids:
        stock_res = await session.execute(
            select(StockBalance).where(StockBalance.material_id.in_(material_ids))
        )
        for s in stock_res.scalars().all():
            stock_map[s.material_id] += float(s.quantity) - float(s.reserved_quantity)

    # Суммарная потребность в материале по всем работам
    total_demand: Dict[int, float] = defaultdict(float)
    for w in works:
        for m in norm_map.get(w.work_type_id, []):
            total_demand[m["material_id"]] += m["norm_value"] * float(w.volume)

    # ── Формирование параметров симуляции ─────────────────────────────────────
    sim_works: List[Dict] = []
    for w in works:
        rp = risk_params.get(w.work_id)
        if rp and rp.alpha and rp.beta_param:
            alpha_, beta__, a_, b_ = (
                float(rp.alpha), float(rp.beta_param), float(rp.a_i), float(rp.b_i)
            )
        else:
            dur = float(w.duration)
            a_, b_ = dur * 0.85, dur * 1.15
            _, _, alpha_, beta__ = _compute_beta_params(a_, dur, b_)

        sim_works.append({
            "work_id": w.work_id,
            "predecessors": predecessors_map[w.work_id],
            "materials": norm_map.get(w.work_type_id, []),
            "alpha": alpha_,
            "beta_": beta__,
            "a": a_,
            "b": b_,
        })

    sim_materials: Dict[int, Dict] = {
        mid: {
            "initial_stock": stock_map.get(mid, 0.0),
            "total_demand": total_demand.get(mid, 0.0),
            "suppliers": mat_suppliers.get(mid, []),
        }
        for mid in material_ids
    }

    topo_order = _topological_sort(sim_works)
    if len(topo_order) != len(sim_works):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Граф работ содержит цикл — расчёт невозможен")

    sim_params: Dict[str, Any] = {
        "works": sim_works,
        "materials": sim_materials,
        "topo_order": topo_order,
    }

    # ── Шаг 3: Создание записи MonteCarloRun ─────────────────────────────────
    run = MonteCarloRun(
        project_id=project_id,
        iterations_count=iterations,
        seed=seed,
        t_plan=t_plan,
    )
    session.add(run)
    await session.flush()  # получить run_id
    run_id: int = run.run_id

    # ── Шаг 4: R итераций Монте-Карло в ProcessPoolExecutor ──────────────────
    n_workers = min(os.cpu_count() or 1, 4)
    base_seed = seed if seed is not None else 42
    chunk_sizes = [iterations // n_workers] * n_workers
    chunk_sizes[-1] += iterations - sum(chunk_sizes)      # остаток в последнем чанке
    seed_starts = [base_seed + i * (iterations // n_workers) for i in range(n_workers)]

    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = [
            loop.run_in_executor(pool, _simulate_chunk, sim_params, seed_starts[i], chunk_sizes[i])
            for i in range(n_workers)
        ]
        chunk_results: List[List[Tuple[float, List[int]]]] = await asyncio.gather(*futures)

    all_results: List[Tuple[float, List[int]]] = [
        item for chunk in chunk_results for item in chunk
    ]

    # ── Шаг 4g: Сохранение итераций в risk.monte_carlo_iteration ─────────────
    iter_rows = [
        {
            "run_id": run_id,
            "iteration_num": r,
            "t_result": all_results[r][0],
            "critical_path": all_results[r][1],
        }
        for r in range(len(all_results))
    ]
    await session.execute(insert(MonteCarloIteration), iter_rows)

    # ── Шаг 5: Показатели риска (формулы 2.46–2.48) ──────────────────────────
    t_arr = np.array([res[0] for res in all_results], dtype=float)
    mean_t = float(np.mean(t_arr))
    std_t = float(np.std(t_arr, ddof=1))
    prob = float(np.sum(t_arr <= t_plan) / len(t_arr))

    run.mean_duration = mean_t
    run.std_duration = std_t
    run.prob_on_time = prob

    # ── Шаг 6: Квантили T_γ (формула 2.49) ───────────────────────────────────
    gamma_levels = [0.5, 0.8, 0.9]
    t_quantiles = np.quantile(t_arr, gamma_levels).tolist()
    for gamma, t_g in zip(gamma_levels, t_quantiles):
        session.add(RiskQuantile(run_id=run_id, gamma_level=gamma, t_gamma=float(t_g)))

    # ── Шаг 7: Индексы критичности CI_i (формула 2.50) ───────────────────────
    crit_count: Dict[int, int] = defaultdict(int)
    for _, critical_wids in all_results:
        for wid in critical_wids:
            crit_count[wid] += 1

    r_total = len(all_results)
    ci_objects: List[WorkCriticalityIndex] = []
    for wid in work_ids:
        ci = crit_count[wid] / r_total
        ci_objects.append(
            WorkCriticalityIndex(
                run_id=run_id,
                work_id=wid,
                criticality_index=ci,
                risk_critical=(ci > 0.5),
            )
        )
    session.add_all(ci_objects)
    await session.commit()

    # ── Формирование ответа ───────────────────────────────────────────────────
    top_critical = sorted(ci_objects, key=lambda x: x.criticality_index, reverse=True)[:10]

    t_sorted = np.sort(t_arr)
    n = len(t_sorted)
    step = max(1, n // 200)
    cdf_points = [
        CDFPoint(t=float(t_sorted[i]), F=float((i + 1) / n))
        for i in range(0, n, step)
    ]
    # Гарантируем последнюю точку (t_max, 1.0)
    if not cdf_points or cdf_points[-1].t < float(t_sorted[-1]):
        cdf_points.append(CDFPoint(t=float(t_sorted[-1]), F=1.0))

    return MonteCarloResponse(
        run_id=run_id,
        mean_duration=mean_t,
        std_duration=std_t,
        prob_on_time=prob,
        t_quantile_50=float(t_quantiles[0]),
        t_quantile_80=float(t_quantiles[1]),
        t_quantile_90=float(t_quantiles[2]),
        top_critical_works=[
            CriticalWorkItem(
                work_id=c.work_id,
                criticality_index=round(c.criticality_index, 4),
                risk_critical=c.risk_critical,
            )
            for c in top_critical
        ],
        cdf=cdf_points,
    )
