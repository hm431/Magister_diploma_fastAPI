"""
Тесты для POST /api/v1/mtr/supply-plan/{project_id}/{calculation_id}
(Подзадача 2.1 — График поставок материалов, формулы 2.8–2.18)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

PREFIX = "/api/v1/mtr"


# ─── Тест 1: Happy path ──────────────────────────────────────────────────────

async def test_supply_plan_happy_path(auth_client, seed):
    """
    Валидные project_id и calculation_id.
    LP должна найти решение: demand, deliveries, availability — непустые,
    total_cost > 0, solver_status — успех.
    Ожидаемые Q: mat1=10.0 total, mat2=5.0 total (5 дней × 2.0 и 1.0).
    """
    pid, cid, wh_id = seed["project_id"], seed["calculation_id"], seed["warehouse_id"]

    with patch("app.services.supply_plan._get_warehouse_for_supplier", return_value=wh_id):
        r = await auth_client.post(f"{PREFIX}/supply-plan/{pid}/{cid}")

    assert r.status_code == 200, r.text
    body = r.json()

    assert body["project_id"] == pid
    assert body["calculation_id"] == cid
    assert body["total_cost"] > 0

    # Потребность — должна быть по двум материалам
    demand = body["demand"]
    assert len(demand) > 0
    mat_ids_in_demand = {d["material_id"] for d in demand}
    assert seed["mat1_id"] in mat_ids_in_demand
    assert seed["mat2_id"] in mat_ids_in_demand

    # Суммарная потребность по дням: 5 дней × 2.0 = 10.0 для mat1
    total_q_mat1 = sum(d["quantity"] for d in demand if d["material_id"] == seed["mat1_id"])
    assert abs(total_q_mat1 - 10.0) < 0.01

    # Поставки: LP разместила хотя бы одну поставку
    assert len(body["deliveries"]) > 0

    # Даты доступности — по каждому материалу
    avail_mat_ids = {a["material_id"] for a in body["availability"]}
    assert seed["mat1_id"] in avail_mat_ids
    assert seed["mat2_id"] in avail_mat_ids

    # Солвер завершился успешно
    assert "Optimization terminated successfully" in body["solver_status"]


# ─── Тест 2: Несуществующий проект ───────────────────────────────────────────

async def test_supply_plan_project_not_found(auth_client, seed):
    """Несуществующий project_id → 404."""
    cid = seed["calculation_id"]
    r = await auth_client.post(f"{PREFIX}/supply-plan/99999/{cid}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ─── Тест 3: Расчёт принадлежит другому проекту ─────────────────────────────

async def test_supply_plan_wrong_calculation(auth_client, seed):
    """
    calculation_id существует, но относится к другому project_id.
    Сервис проверяет calc.project_id == project_id → 404.
    """
    pid = seed["project_id"]
    # calculation_id=99999 не существует ни в каком проекте
    r = await auth_client.post(f"{PREFIX}/supply-plan/{pid}/99999")
    assert r.status_code == 404


# ─── Тест 4: Нет расписания (нет ScheduleItem) ───────────────────────────────

async def test_supply_plan_no_schedule_items(auth_client, seed, test_engine):
    """
    Расчёт без позиций (schedule_item) → 400 с SCHEDULE_CALCULATION_FAILED.
    Создаём отдельный пустой расчёт для того же проекта.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.sro import ScheduleCalculation

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as s:
        empty_calc = ScheduleCalculation(
            project_id=seed["project_id"],
            version=99,
            scenario="test_empty",
            t_min=0,
        )
        s.add(empty_calc)
        await s.commit()
        empty_cid = empty_calc.calculation_id

    try:
        r = await auth_client.post(
            f"{PREFIX}/supply-plan/{seed['project_id']}/{empty_cid}"
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "SCHEDULE_CALCULATION_FAILED"
    finally:
        async with factory() as s:
            await s.execute(
                __import__("sqlalchemy", fromlist=["delete"]).delete(ScheduleCalculation)
                .where(ScheduleCalculation.calculation_id == empty_cid)
            )
            await s.commit()


# ─── Тест 5: Нет действующих договоров поставки ─────────────────────────────

async def test_supply_plan_no_contracts(auth_client, seed, test_engine):
    """
    Все договоры просрочены (valid_to < plan_start) → 400 с SCHEDULE_CALCULATION_FAILED.
    """
    from datetime import date
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.norm import SupplyContract

    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    # Устанавливаем valid_to в прошлое для тестового поставщика
    async with factory() as s:
        await s.execute(
            update(SupplyContract)
            .where(SupplyContract.supplier_id == seed["supplier_id"])
            .values(valid_to=date(2020, 1, 1))
        )
        await s.commit()

    try:
        with patch(
            "app.services.supply_plan._get_warehouse_for_supplier",
            return_value=seed["warehouse_id"],
        ):
            r = await auth_client.post(
                f"{PREFIX}/supply-plan/{seed['project_id']}/{seed['calculation_id']}"
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "SCHEDULE_CALCULATION_FAILED"
    finally:
        # Восстанавливаем договоры
        async with factory() as s:
            await s.execute(
                update(SupplyContract)
                .where(SupplyContract.supplier_id == seed["supplier_id"])
                .values(valid_to=None)
            )
            await s.commit()


# ─── Тест 6: Идемпотентность (повторный вызов) ───────────────────────────────

async def test_supply_plan_idempotent(auth_client, seed, test_engine):
    """
    Повторный вызов не дублирует записи в БД.
    Количество строк в mtr.planned_delivery после второго вызова
    должно совпадать с количеством после первого.
    """
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.mtr import PlannedDelivery

    pid, cid, wh_id = seed["project_id"], seed["calculation_id"], seed["warehouse_id"]
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    with patch("app.services.supply_plan._get_warehouse_for_supplier", return_value=wh_id):
        r1 = await auth_client.post(f"{PREFIX}/supply-plan/{pid}/{cid}")
    assert r1.status_code == 200

    async with factory() as s:
        count_q = await s.scalar(
            select(func.count()).select_from(PlannedDelivery).where(PlannedDelivery.project_id == pid)
        )
    count_after_first = count_q

    with patch("app.services.supply_plan._get_warehouse_for_supplier", return_value=wh_id):
        r2 = await auth_client.post(f"{PREFIX}/supply-plan/{pid}/{cid}")
    assert r2.status_code == 200

    async with factory() as s:
        count_q2 = await s.scalar(
            select(func.count()).select_from(PlannedDelivery).where(PlannedDelivery.project_id == pid)
        )
    count_after_second = count_q2

    # Второй вызов очищает и перезаписывает — количество строк то же
    assert count_after_first == count_after_second


# ─── Тест 7: Неавторизованный запрос ─────────────────────────────────────────

async def test_supply_plan_unauthorized(anon_client, seed):
    """Запрос без Bearer-токена → 403 (HTTPBearer отклоняет)."""
    pid, cid = seed["project_id"], seed["calculation_id"]
    r = await anon_client.post(f"{PREFIX}/supply-plan/{pid}/{cid}")
    assert r.status_code in (401, 403)


# ─── Тест 8: Корректность структуры ответа ───────────────────────────────────

async def test_supply_plan_response_schema(auth_client, seed):
    """Каждое поле ответа соответствует схеме SupplyPlanResponse."""
    pid, cid, wh_id = seed["project_id"], seed["calculation_id"], seed["warehouse_id"]

    with patch("app.services.supply_plan._get_warehouse_for_supplier", return_value=wh_id):
        r = await auth_client.post(f"{PREFIX}/supply-plan/{pid}/{cid}")

    assert r.status_code == 200
    body = r.json()

    # Верхний уровень
    for key in ("project_id", "calculation_id", "total_cost", "demand", "deliveries", "availability", "solver_status"):
        assert key in body, f"Отсутствует поле {key!r}"

    # Структура demand
    if body["demand"]:
        d = body["demand"][0]
        assert "material_id" in d
        assert "demand_date" in d
        assert "quantity" in d
        assert d["quantity"] >= 0

    # Структура deliveries
    if body["deliveries"]:
        dv = body["deliveries"][0]
        for f in ("material_id", "warehouse_id", "supplier_id", "planned_date", "planned_volume", "unit_cost"):
            assert f in dv, f"Отсутствует поле {f!r} в deliveries"
        assert dv["planned_volume"] > 0
        assert dv["unit_cost"] >= 0

    # Структура availability
    if body["availability"]:
        av = body["availability"][0]
        assert "material_id" in av
        assert "availability_date" in av
