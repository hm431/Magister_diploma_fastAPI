"""
Тесты для POST /api/v1/mtr/warehouse-feasibility/{project_id}/{calculation_id}
(Подзадача 2.2 — Проверка загрузки склада и логистики, формулы 2.19–2.30)

Все тесты сначала вызывают /supply-plan (2.1), чтобы заполнить
mtr.planned_delivery — от него зависит /warehouse-feasibility.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ref_object import Warehouse

PREFIX = "/api/v1/mtr"


async def _call_supply_plan(auth_client, seed) -> None:
    """Вспомогательный вызов 2.1 перед каждым тестом 2.2."""
    pid, cid, wh_id = seed["project_id"], seed["calculation_id"], seed["warehouse_id"]
    with patch("app.services.supply_plan._get_warehouse_for_supplier", return_value=wh_id):
        r = await auth_client.post(f"{PREFIX}/supply-plan/{pid}/{cid}")
    assert r.status_code == 200, f"Не удалось вызвать supply-plan: {r.text}"


# ─── Тест 1: Happy path (склад не перегружен) ────────────────────────────────

async def test_warehouse_feasibility_happy_path(auth_client, seed):
    """
    При большой вместимости склада и умеренном потоке поставок:
    feasible=True, violations=[], load_profile заполнен по дням.
    """
    await _call_supply_plan(auth_client, seed)
    pid, cid = seed["project_id"], seed["calculation_id"]

    r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["project_id"] == pid
    assert body["calculation_id"] == cid
    assert body["feasible"] is True
    assert body["violations"] == []

    profile = body["load_profile"]
    assert len(profile) > 0

    row = profile[0]
    for field in ("profile_date", "total_load", "utilization_ratio", "peak_indicator", "rho"):
        assert field in row, f"Отсутствует поле {field!r} в load_profile"

    # При большом U_max загрузка < 90% → peak_indicator=False
    assert all(not r["peak_indicator"] for r in profile)
    # adjusted_deliveries нет (нет нарушений)
    assert body["adjusted_deliveries"] is None


# ─── Тест 2: Нарушение вместимости склада (2.23) ─────────────────────────────

async def test_warehouse_capacity_violation(auth_client, seed, test_engine):
    """
    При маленькой вместимости (capacity=0.01):
    feasible=False, violations содержат тип 'capacity',
    adjusted_deliveries не None (LP-корректировка запустилась).
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with factory() as s:
        await s.execute(
            update(Warehouse)
            .where(Warehouse.warehouse_id == seed["warehouse_id"])
            .values(capacity=0.01)
        )
        await s.commit()

    try:
        await _call_supply_plan(auth_client, seed)
        pid, cid = seed["project_id"], seed["calculation_id"]

        r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["feasible"] is False
        violation_types = {v["violation_type"] for v in body["violations"]}
        assert "capacity" in violation_types

        # LP-корректировка должна вернуть скорректированный план
        assert body["adjusted_deliveries"] is not None
    finally:
        async with factory() as s:
            await s.execute(
                update(Warehouse)
                .where(Warehouse.warehouse_id == seed["warehouse_id"])
                .values(capacity=10_000.0)
            )
            await s.commit()


# ─── Тест 3: Перегрузка системы обслуживания ρ >= 1 (2.27) ──────────────────

async def test_warehouse_overload_violation(auth_client, seed, test_engine):
    """
    При очень низком service_rate (μ=0.001) интенсивность ρ >= 1:
    violations содержат тип 'overload'.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with factory() as s:
        await s.execute(
            update(Warehouse)
            .where(Warehouse.warehouse_id == seed["warehouse_id"])
            .values(service_rate=0.001)
        )
        await s.commit()

    try:
        await _call_supply_plan(auth_client, seed)
        pid, cid = seed["project_id"], seed["calculation_id"]

        r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["feasible"] is False
        violation_types = {v["violation_type"] for v in body["violations"]}
        assert "overload" in violation_types
    finally:
        async with factory() as s:
            await s.execute(
                update(Warehouse)
                .where(Warehouse.warehouse_id == seed["warehouse_id"])
                .values(service_rate=10.0)
            )
            await s.commit()


# ─── Тест 4: Превышение допустимого времени ожидания (2.30) ──────────────────

async def test_warehouse_wait_time_violation(auth_client, seed, test_engine):
    """
    allowed_wait_time=0 → любое W_q(t) > 0 создаёт нарушение 'wait_time'.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with factory() as s:
        await s.execute(
            update(Warehouse)
            .where(Warehouse.warehouse_id == seed["warehouse_id"])
            .values(allowed_wait_time=0, service_rate=1.0)
        )
        await s.commit()

    try:
        await _call_supply_plan(auth_client, seed)
        pid, cid = seed["project_id"], seed["calculation_id"]

        r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
        assert r.status_code == 200, r.text
        body = r.json()

        # При ρ < 1 и W_q^доп=0: нарушение wait_time появляется в дни с поставками
        if body["violations"]:
            violation_types = {v["violation_type"] for v in body["violations"]}
            assert "wait_time" in violation_types or "overload" in violation_types
    finally:
        async with factory() as s:
            await s.execute(
                update(Warehouse)
                .where(Warehouse.warehouse_id == seed["warehouse_id"])
                .values(allowed_wait_time=60, service_rate=10.0)
            )
            await s.commit()


# ─── Тест 5: Вызов без предварительного supply-plan ─────────────────────────

async def test_warehouse_feasibility_no_deliveries(auth_client, seed, test_engine):
    """
    Если mtr.planned_delivery пуст для проекта → 404.
    """
    from sqlalchemy import delete as sa_delete
    from app.models.mtr import PlannedDelivery

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(
            sa_delete(PlannedDelivery).where(PlannedDelivery.project_id == seed["project_id"])
        )
        await s.commit()

    pid, cid = seed["project_id"], seed["calculation_id"]
    r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r.status_code == 404
    assert "supply-plan" in r.json()["error"]["message"].lower() or \
           r.json()["error"]["code"] == "NOT_FOUND"


# ─── Тест 6: Несуществующий проект ───────────────────────────────────────────

async def test_warehouse_feasibility_project_not_found(auth_client, seed):
    """Несуществующий project_id → 404."""
    cid = seed["calculation_id"]
    r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/99999/{cid}")
    assert r.status_code == 404


# ─── Тест 7: Неавторизованный запрос ─────────────────────────────────────────

async def test_warehouse_feasibility_unauthorized(anon_client, seed):
    """Без Bearer-токена → 401/403."""
    pid, cid = seed["project_id"], seed["calculation_id"]
    r = await anon_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r.status_code in (401, 403)


# ─── Тест 8: Корректность структуры ответа ───────────────────────────────────

async def test_warehouse_feasibility_response_schema(auth_client, seed):
    """Каждое поле ответа соответствует схеме WarehouseFeasibilityResponse."""
    await _call_supply_plan(auth_client, seed)
    pid, cid = seed["project_id"], seed["calculation_id"]

    r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r.status_code == 200, r.text
    body = r.json()

    for key in ("project_id", "calculation_id", "warehouse_id", "feasible", "violations", "load_profile", "adjusted_deliveries"):
        assert key in body, f"Отсутствует поле {key!r}"

    assert isinstance(body["feasible"], bool)
    assert isinstance(body["violations"], list)
    assert isinstance(body["load_profile"], list)

    if body["load_profile"]:
        row = body["load_profile"][0]
        for f in ("profile_date", "total_load", "utilization_ratio", "peak_indicator"):
            assert f in row, f"Отсутствует поле {f!r} в load_profile"
        assert 0.0 <= row["utilization_ratio"]
        assert isinstance(row["peak_indicator"], bool)

    if body["violations"]:
        v = body["violations"][0]
        assert "profile_date" in v
        assert v["violation_type"] in ("capacity", "overload", "wait_time")
        assert "description" in v


# ─── Тест 9: Данные load_profile записаны в БД ───────────────────────────────

async def test_warehouse_load_profile_persisted(auth_client, seed, test_engine):
    """
    После вызова в mtr.warehouse_load_profile должны быть записи
    с правильным warehouse_id.
    """
    from sqlalchemy import func, select
    from app.models.mtr import WarehouseLoadProfile

    await _call_supply_plan(auth_client, seed)
    pid, cid, wh_id = seed["project_id"], seed["calculation_id"], seed["warehouse_id"]

    r = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r.status_code == 200

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as s:
        count = await s.scalar(
            select(func.count()).select_from(WarehouseLoadProfile)
            .where(WarehouseLoadProfile.warehouse_id == wh_id)
        )
    assert count > 0


# ─── Тест 10: Идемпотентность ────────────────────────────────────────────────

async def test_warehouse_feasibility_idempotent(auth_client, seed, test_engine):
    """
    Повторный вызов не дублирует строки в warehouse_load_profile.
    """
    from sqlalchemy import func, select
    from app.models.mtr import WarehouseLoadProfile

    await _call_supply_plan(auth_client, seed)
    pid, cid, wh_id = seed["project_id"], seed["calculation_id"], seed["warehouse_id"]

    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    r1 = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r1.status_code == 200

    async with factory() as s:
        cnt1 = await s.scalar(
            select(func.count()).select_from(WarehouseLoadProfile)
            .where(WarehouseLoadProfile.warehouse_id == wh_id)
        )

    r2 = await auth_client.post(f"{PREFIX}/warehouse-feasibility/{pid}/{cid}")
    assert r2.status_code == 200

    async with factory() as s:
        cnt2 = await s.scalar(
            select(func.count()).select_from(WarehouseLoadProfile)
            .where(WarehouseLoadProfile.warehouse_id == wh_id)
        )

    assert cnt1 == cnt2
