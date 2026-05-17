"""
Фикстуры для интеграционных тестов MTR-подсистемы.

Тесты работают против реальной PostgreSQL (diploma или TEST_DATABASE_URL).
Все тестовые записи помечены именами с префиксом TEST_ и удаляются в teardown.

Перед запуском:
    export TEST_DATABASE_URL=postgresql+asyncpg://admin:admin123@localhost:5432/diploma
    pytest tests/
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import AsyncGenerator, Dict

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app
from app.models.mtr import StockBalance, WarehouseLoadProfile
from app.models.norm import ConsumptionNorm, SupplyContract, TransportParam
from app.models.ref_object import Material, ObjectRef, Site, Supplier, Warehouse, WorkType
from app.models.sro import (
    Project,
    ScheduleCalculation,
    ScheduleItem,
    Work,
)
from app.models.user import User

_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://admin:admin123@localhost:5432/diploma",
)

_SCHEMAS = ["ref", "norm", "sro", "mtr", "ops", "risk"]


# ─── Движок (один на всю сессию pytest) ─────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        for schema in _SCHEMAS:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


# ─── Тестовые данные (seed) — создаются и удаляются для каждого теста ───────

@pytest_asyncio.fixture
async def seed(test_engine) -> AsyncGenerator[Dict, None]:
    """
    Создаёт минимальный набор связанных записей для тестирования MTR.
    Горизонт: 5 дней, 2 материала, 1 поставщик, 1 склад.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with factory() as s:
        # ── справочники ──────────────────────────────────────────────────
        obj = ObjectRef(name="TEST_OBJ", type="test", address="TEST_ADDRESS")
        s.add(obj)
        await s.flush()

        site = Site(object_id=obj.object_id, name="TEST_SITE")
        s.add(site)
        await s.flush()

        wt = WorkType(name="TEST_WORK_TYPE", unit="м3")
        s.add(wt)
        await s.flush()

        mat1 = Material(name="TEST_MAT_1", unit="т", storage_coefficient=0.5)
        mat2 = Material(name="TEST_MAT_2", unit="м3", storage_coefficient=0.3)
        s.add_all([mat1, mat2])
        await s.flush()

        # Склад с достаточной вместимостью (нарушений нет в happy-path)
        wh = Warehouse(
            name="TEST_WAREHOUSE",
            capacity=10_000.0,
            loading_posts=3,
            service_rate=10.0,
            allowed_wait_time=60,
        )
        s.add(wh)
        await s.flush()

        sup = Supplier(name="TEST_SUPPLIER")
        s.add(sup)
        await s.flush()

        # ── проект и работы ──────────────────────────────────────────────
        proj = Project(
            object_id=obj.object_id,
            plan_start=date(2025, 1, 1),
            plan_finish=date(2025, 12, 31),
            status="planned",
        )
        s.add(proj)
        await s.flush()

        # Работа 1: d=3, v=30  → дни 1-3 (ES=0, EF=3)
        # Работа 2: d=2, v=20  → дни 4-5 (ES=3, EF=5)
        w1 = Work(
            project_id=proj.project_id,
            site_id=site.site_id,
            work_type_id=wt.work_type_id,
            duration=3,
            volume=30.0,
        )
        w2 = Work(
            project_id=proj.project_id,
            site_id=site.site_id,
            work_type_id=wt.work_type_id,
            duration=2,
            volume=20.0,
        )
        s.add_all([w1, w2])
        await s.flush()

        calc = ScheduleCalculation(
            project_id=proj.project_id,
            version=1,
            scenario="plan",
            t_min=5,
        )
        s.add(calc)
        await s.flush()

        s.add_all([
            ScheduleItem(
                calculation_id=calc.calculation_id,
                work_id=w1.work_id,
                es=0, ef=3, ls=0, lf=3, tf=0, is_critical=True,
            ),
            ScheduleItem(
                calculation_id=calc.calculation_id,
                work_id=w2.work_id,
                es=3, ef=5, ls=3, lf=5, tf=0, is_critical=True,
            ),
        ])

        # ── нормы расхода: r(mat1)=0.2, r(mat2)=0.1 ─────────────────────
        # Ожидаемые Q:  mat1=2.0/день, mat2=1.0/день → итого 10.0 и 5.0
        s.add_all([
            ConsumptionNorm(
                work_type_id=wt.work_type_id,
                material_id=mat1.material_id,
                effective_from=date(2024, 1, 1),
                norm_value=0.2,
            ),
            ConsumptionNorm(
                work_type_id=wt.work_type_id,
                material_id=mat2.material_id,
                effective_from=date(2024, 1, 1),
                norm_value=0.1,
            ),
        ])

        # ── договоры: c(mat1)=100, c(mat2)=200, W=50/25, τ^мин=1 ─────────
        s.add_all([
            SupplyContract(
                supplier_id=sup.supplier_id,
                material_id=mat1.material_id,
                price_per_unit=100.0,
                min_delivery_days=1,
                max_volume_per_period=50.0,
                valid_from=date(2024, 1, 1),
            ),
            SupplyContract(
                supplier_id=sup.supplier_id,
                material_id=mat2.material_id,
                price_per_unit=200.0,
                min_delivery_days=1,
                max_volume_per_period=25.0,
                valid_from=date(2024, 1, 1),
            ),
        ])

        # ── транспортные параметры: q(mat1)=5, q(mat2)=3 ─────────────────
        s.add_all([
            TransportParam(
                material_id=mat1.material_id,
                warehouse_id=wh.warehouse_id,
                avg_capacity=5.0,
                avg_delivery_time=1,
            ),
            TransportParam(
                material_id=mat2.material_id,
                warehouse_id=wh.warehouse_id,
                avg_capacity=3.0,
                avg_delivery_time=1,
            ),
        ])

        # ── начальные остатки: S0(mat1)=3.0, S0(mat2)=2.0 ───────────────
        s.add_all([
            StockBalance(
                material_id=mat1.material_id,
                warehouse_id=wh.warehouse_id,
                balance_date=date(2025, 1, 1),
                quantity=3.0,
                reserved_quantity=0.0,
            ),
            StockBalance(
                material_id=mat2.material_id,
                warehouse_id=wh.warehouse_id,
                balance_date=date(2025, 1, 1),
                quantity=2.0,
                reserved_quantity=0.0,
            ),
        ])

        await s.commit()

        ids: Dict = {
            "project_id":    proj.project_id,
            "calculation_id": calc.calculation_id,
            "warehouse_id":  wh.warehouse_id,
            "mat1_id":       mat1.material_id,
            "mat2_id":       mat2.material_id,
            "supplier_id":   sup.supplier_id,
            "object_id":     obj.object_id,
            "site_id":       site.site_id,
            "work_type_id":  wt.work_type_id,
        }

    yield ids

    # ── teardown: удаляем тестовые данные ────────────────────────────────
    async with factory() as s:
        mat_ids = [ids["mat1_id"], ids["mat2_id"]]

        await s.execute(delete(Project).where(Project.project_id == ids["project_id"]))
        await s.execute(delete(WarehouseLoadProfile).where(WarehouseLoadProfile.warehouse_id == ids["warehouse_id"]))
        await s.execute(delete(TransportParam).where(TransportParam.material_id.in_(mat_ids)))
        await s.execute(delete(SupplyContract).where(SupplyContract.material_id.in_(mat_ids)))
        await s.execute(delete(ConsumptionNorm).where(ConsumptionNorm.material_id.in_(mat_ids)))
        await s.execute(delete(StockBalance).where(StockBalance.material_id.in_(mat_ids)))
        await s.execute(delete(Material).where(Material.material_id.in_(mat_ids)))
        await s.execute(delete(Warehouse).where(Warehouse.warehouse_id == ids["warehouse_id"]))
        await s.execute(delete(Supplier).where(Supplier.supplier_id == ids["supplier_id"]))
        await s.execute(delete(WorkType).where(WorkType.work_type_id == ids["work_type_id"]))
        await s.execute(delete(Site).where(Site.site_id == ids["site_id"]))
        await s.execute(delete(ObjectRef).where(ObjectRef.object_id == ids["object_id"]))
        await s.commit()


# ─── Клиенты ────────────────────────────────────────────────────────────────

def _make_mock_user() -> User:
    return User(
        user_id=9999,
        username="test_user",
        email="test@test.com",
        hashed_password="x",
        role="admin",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest_asyncio.fixture
async def auth_client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient с подменённой авторизацией (без seed-данных)."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    mock_user = _make_mock_user()

    async def _override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient без авторизации — для проверки 401/403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
