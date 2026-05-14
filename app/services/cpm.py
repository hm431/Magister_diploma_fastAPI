"""
Расчёт CPM с сохранением результата в БД.
Формулы (2.1)-(2.5) из подраздела 2.3.1.
"""
from __future__ import annotations
from typing import Dict, List

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.sro import (
    Project, Work, WorkPredecessor,
    ScheduleCalculation, ScheduleItem,
)
from app.core.exceptions import (
    CyclicDependencyError, ScheduleCalculationError, ProjectNotFoundError,
)


async def calculate_and_save_cpm(
    project_id: int,
    session: AsyncSession,
    scenario: str = "plan",
) -> ScheduleCalculation:
    """
    Загружает работы и связи проекта из БД, считает CPM,
    сохраняет результат как новую версию ScheduleCalculation.
    """
    # === 1. Проверка проекта ===
    project = await session.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError(project_id)

    # === 2. Загрузка работ и предшественников ===
    works_query = (
        select(Work)
        .where(Work.project_id == project_id)
        .options(selectinload(Work.predecessors))
    )
    works: List[Work] = (await session.scalars(works_query)).all()

    if not works:
        raise ScheduleCalculationError(message=f"У проекта {project_id} нет работ")

    # === 3. Построение графа ===
    graph = nx.DiGraph()
    durations: Dict[int, int] = {}
    for w in works:
        graph.add_node(w.work_id)
        durations[w.work_id] = w.duration
        for pred in w.predecessors:
            graph.add_edge(pred.predecessor_work_id, w.work_id)

    # === 4. Проверка ацикличности ===
    if not nx.is_directed_acyclic_graph(graph):
        cycle = nx.find_cycle(graph)
        raise CyclicDependencyError(
            details={"cycle_edges": [(u, v) for u, v in cycle]}
        )

    topo_order = list(nx.topological_sort(graph))

    # === 5. Прямой проход — ES, EF (2.1)-(2.2) ===
    es: Dict[int, int] = {}
    ef: Dict[int, int] = {}
    for node in topo_order:
        preds = list(graph.predecessors(node))
        es[node] = max((ef[p] for p in preds), default=0)
        ef[node] = es[node] + durations[node]

    t_min = max(ef.values())

    # === 6. Обратный проход — LS, LF (2.3)-(2.4) ===
    ls: Dict[int, int] = {}
    lf: Dict[int, int] = {}
    for node in reversed(topo_order):
        succs = list(graph.successors(node))
        lf[node] = min((ls[s] for s in succs), default=t_min)
        ls[node] = lf[node] - durations[node]

    # === 7. Создаём запись расчёта ===
    # Определяем следующий номер версии
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
    await session.flush()   # чтобы получить calculation_id

    # === 8. Сохраняем элементы расписания ===
    for w in works:
        tf = ls[w.work_id] - es[w.work_id]                          # формула (2.5)
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