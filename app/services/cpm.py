"""
Расчёт CPM с сохранением результата в БД.
Формулы (2.1)–(2.6) из подраздела 2.3.1.
  2.1  ES_i = max(EF_p для p ∈ P_i)
  2.2  EF_i = ES_i + d_i
  2.3  LF_i = min(LS_s для s ∈ S_i)
  2.4  LS_i = LF_i − d_i
  2.5  TF_i = LS_i − ES_i
  2.6  ES_i >= max(T_доступ(j)) для j : r_ij > 0  (ресурсное ограничение)
"""
from __future__ import annotations
from typing import Dict, List

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mtr import MaterialAvailabilityDate
from app.models.norm import ConsumptionNorm
from app.models.sro import (
    Project, Work, WorkPredecessor,
    ScheduleCalculation, ScheduleItem,
)
from app.core.exceptions import (
    CyclicDependencyError, ScheduleCalculationError, ProjectNotFoundError,
)

_MAX_ITER = 20   # максимум итераций для сходимости ресурсного ограничения


async def calculate_and_save_cpm(
    project_id: int,
    session: AsyncSession,
    scenario: str = "plan",
) -> ScheduleCalculation:
    """
    Загружает работы и связи проекта из БД, считает CPM,
    сохраняет результат как новую версию ScheduleCalculation.

    Если для проекта уже есть записи mtr.material_availability_date
    (т.е. задача 2.1 была выполнена ранее), применяет формулу 2.6
    и итерирует прямой проход до сходимости ES_i.
    """
    # ── 1. Проверка проекта ──────────────────────────────────────────────────
    project = await session.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError(project_id)

    plan_start = project.plan_start

    # ── 2. Загрузка работ и предшественников ─────────────────────────────────
    works_query = (
        select(Work)
        .where(Work.project_id == project_id)
        .options(selectinload(Work.predecessors))
    )
    works: List[Work] = (await session.scalars(works_query)).all()

    if not works:
        raise ScheduleCalculationError(message=f"У проекта {project_id} нет работ")

    # ── 3. Построение графа ──────────────────────────────────────────────────
    graph = nx.DiGraph()
    durations: Dict[int, int] = {}
    for w in works:
        graph.add_node(w.work_id)
        durations[w.work_id] = w.duration
        for pred in w.predecessors:
            graph.add_edge(pred.predecessor_work_id, w.work_id)

    if not nx.is_directed_acyclic_graph(graph):
        cycle = nx.find_cycle(graph)
        raise CyclicDependencyError(
            details={"cycle_edges": [(u, v) for u, v in cycle]}
        )

    topo_order = list(nx.topological_sort(graph))

    # ── 4. Формула 2.6: T_доступ(j) из последнего расчёта supply_plan ───────
    # Загружаем MaterialAvailabilityDate (если supply_plan ещё не запускался,
    # таблица пуста — работаем без ресурсного ограничения).
    avail_rows = (
        await session.scalars(
            select(MaterialAvailabilityDate)
            .where(MaterialAvailabilityDate.project_id == project_id)
            .order_by(
                MaterialAvailabilityDate.calculation_id.desc(),
                MaterialAvailabilityDate.material_id,
            )
        )
    ).all()

    # Берём последний calculation_id — самый свежий plan supply
    avail_by_mat: Dict[int, int] = {}   # material_id → день от plan_start
    if avail_rows:
        latest_calc_id = avail_rows[0].calculation_id
        for ar in avail_rows:
            if ar.calculation_id == latest_calc_id and ar.material_id not in avail_by_mat:
                avail_by_mat[ar.material_id] = (ar.availability_date - plan_start).days

    # ── 5. Нормы расхода: work_type_id → [material_id] для формулы 2.6 ──────
    work_mat_needs: Dict[int, List[int]] = {w.work_id: [] for w in works}
    if avail_by_mat:
        norm_rows = (await session.scalars(select(ConsumptionNorm))).all()
        # Только актуальные нормы (нет effective_from-фильтра, берём все)
        wt_to_mats: Dict[int, List[int]] = {}
        for nr in norm_rows:
            if nr.norm_value > 0:
                wt_to_mats.setdefault(nr.work_type_id, []).append(nr.material_id)
        for w in works:
            work_mat_needs[w.work_id] = wt_to_mats.get(w.work_type_id, [])

    # ── 6. Прямой проход с итеративной сходимостью (формулы 2.1–2.2, 2.6) ───
    # Итерируем до тех пор, пока ES_i не стабилизируются (формула 2.6 может
    # менять ES_i → меняются EF предшественников → меняются ES последователей).
    # При отсутствии данных T_доступ сходимость достигается за 1 итерацию.
    es: Dict[int, int] = {}
    ef: Dict[int, int] = {}

    for _iteration in range(_MAX_ITER):
        prev_es = dict(es)
        es = {}
        ef = {}

        for node in topo_order:
            preds = list(graph.predecessors(node))
            pred_ef_val = max((ef[p] for p in preds), default=0)   # формулы 2.1

            # Формула 2.6: ресурсное ограничение по T_доступ(j)
            mat_t = 0
            if avail_by_mat:
                mat_t = max(
                    (avail_by_mat[j]
                     for j in work_mat_needs.get(node, [])
                     if j in avail_by_mat),
                    default=0,
                )

            es[node] = max(pred_ef_val, mat_t)        # формула 2.1 + 2.6
            ef[node] = es[node] + durations[node]     # формула 2.2

        if es == prev_es:   # сходимость
            break

    t_min = max(ef.values())

    # ── 7. Обратный проход — LS, LF (формулы 2.3–2.4) ───────────────────────
    ls: Dict[int, int] = {}
    lf: Dict[int, int] = {}
    for node in reversed(topo_order):
        succs = list(graph.successors(node))
        lf[node] = min((ls[s] for s in succs), default=t_min)
        ls[node] = lf[node] - durations[node]

    # ── 8. Создаём запись расчёта ────────────────────────────────────────────
    last_version_q = select(ScheduleCalculation.version).where(
        ScheduleCalculation.project_id == project_id,
        ScheduleCalculation.scenario == scenario,
    ).order_by(ScheduleCalculation.version.desc()).limit(1)
    last_version = (await session.execute(last_version_q)).scalar()
    next_version = (last_version or 0) + 1

    calculation = ScheduleCalculation(
        project_id=project_id,
        scenario=scenario,
        version=next_version,
        t_min=t_min,
    )
    session.add(calculation)
    await session.flush()

    # ── 9. Сохраняем элементы расписания ─────────────────────────────────────
    for w in works:
        tf = ls[w.work_id] - es[w.work_id]   # формула 2.5
        item = ScheduleItem(
            calculation_id=calculation.calculation_id,
            work_id=w.work_id,
            es=es[w.work_id],
            ef=ef[w.work_id],
            ls=ls[w.work_id],
            lf=lf[w.work_id],
            tf=tf,
            is_critical=(tf == 0),
        )
        session.add(item)

    await session.commit()
    await session.refresh(calculation)
    return calculation
