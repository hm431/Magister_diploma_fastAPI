
#!/usr/bin/env python3
"""
Генератор и загрузчик тестовых данных для PostgreSQL-схемы из вашего DDL.

Зависимость:
    pip install psycopg2-binary

Пример запуска:
    python generate_and_load_kis_demo.py \
        --dsn "host=localhost port=5432 dbname=demo user=postgres password=secret" \
        --truncate \
        --seed 42 \
        --projects 6

Если --dsn не указан, используются DATABASE_URL или PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Установите зависимость: pip install psycopg2-binary") from exc


ROLE_NAMES = ["Администратор", "ПТО", "МТС", "Руководитель"]
OBJECT_TYPES = ["Водозабор", "Насосная станция", "Водопровод", "Коллектор", "Очистные сооружения", "Иное"]
MATERIAL_CATEGORIES = ["Трубы", "Фитинги", "Арматура", "Кабель", "ЖБИ", "Металл", "Химия", "Расходники"]
WORK_GROUPS = ["Земляные работы", "Монтаж", "Пусконаладка", "Сварка", "Благоустройство", "Гидравлика"]
EQUIPMENT_TYPES = ["Экскаватор", "Кран", "Автокран", "Самосвал", "Сварочный аппарат", "Насос", "Буровая установка"]
SUPPLIER_CLASSES = ["A", "B", "C", "D"]
ACT_STATUSES = ["draft", "signed_contractor", "signed_customer", "rejected"]
DELIVERY_STATUSES = ["planned", "confirmed", "shipped", "delivered", "cancelled"]
DEVIATION_CATEGORIES = ["MTR", "weather", "technological", "personnel", "other"]

FIRST_NAMES = ["Алексей", "Иван", "Дмитрий", "Сергей", "Михаил", "Андрей", "Никита", "Павел", "Артём", "Олег", "Роман", "Евгений", "Илья", "Виктор", "Антон"]
LAST_NAMES = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Васильев", "Новиков", "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров"]
PATRONYMICS = ["Алексеевич", "Иванович", "Дмитриевич", "Сергеевич", "Михайлович", "Андреевич", "Никитич", "Павлович", "Артёмович", "Владимирович"]

DEFAULTS = {
    "users": 18,
    "objects": 8,
    "sites_per_object_min": 2,
    "sites_per_object_max": 5,
    "work_types": 18,
    "materials": 28,
    "suppliers": 10,
    "warehouses": 5,
    "brigades": 7,
    "equipment": 16,
    "qualifications": 8,
    "projects_per_object_min": 1,
    "projects_per_object_max": 2,
    "works_per_project_min": 8,
    "works_per_project_max": 16,
    "executions_per_work_min": 1,
    "executions_per_work_max": 3,
    "deliveries_per_project_min": 4,
    "deliveries_per_project_max": 9,
    "monte_carlo_iterations": 200,
}


def connect(dsn: str | None):
    dsn = dsn or os.getenv("DATABASE_URL")
    if not dsn:
        host = os.getenv("PGHOST", "localhost")
        port = os.getenv("PGPORT", "5432")
        dbname = os.getenv("PGDATABASE", "diploma")
        user = os.getenv("PGUSER", "admin")
        password = os.getenv("PGPASSWORD", "admin123")
        dsn = f"host={host} port={port} dbname={dbname} user={user}"
        if password:
            dsn += f" password={password}"
    return psycopg2.connect(dsn)


def rand_date(rng: random.Random, start: date, end: date) -> date:
    if end < start:
        start, end = end, start
    return start + timedelta(days=rng.randint(0, (end - start).days if end > start else 0))


def weighted_choice(rng: random.Random, items: List[str], weights: List[float]) -> str:
    total = sum(weights)
    x = rng.uniform(0, total)
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if x <= acc:
            return item
    return items[-1]


def truncate_all(cur):
    tables = [
        "risk.scenario_action",
        "risk.correction_scenario",
        "risk.risk_quantile",
        "risk.work_criticality_index",
        "risk.monte_carlo_iteration",
        "risk.monte_carlo_run",
        "risk.supplier_delivery_stats",
        "risk.work_risk_params",
        "ops.deviation_cause",
        "ops.deviation",
        "ops.ks3_certificate",
        "ops.ks2_item",
        "ops.ks2_act",
        "ops.work_execution",
        "mtr.material_availability_date",
        "mtr.warehouse_load_profile",
        "mtr.material_demand",
        "mtr.actual_delivery",
        "mtr.planned_delivery",
        "mtr.stock_movement",
        "mtr.stock_balance",
        "sro.equipment_assignment",
        "sro.brigade_assignment",
        "sro.schedule_item",
        "sro.schedule_calculation",
        "sro.work_predecessor",
        "sro.work",
        "sro.project",
        "norm.transport_param",
        "norm.supply_contract",
        "norm.brigade_qualification",
        "norm.consumption_norm",
        "ref.equipment",
        "ref.qualification",
        "ref.brigade",
        "ref.warehouse",
        "ref.supplier",
        "ref.material",
        "ref.work_type",
        "ref.site",
        "ref.object",
        "ref.app_user",
        "ref.role",
    ]
    cur.execute("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE;")


def insert_many(cur, table: str, columns: List[str], rows: List[Tuple], returning: str | None = None) -> List[int]:
    if not rows:
        return []
    cols = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    if returning:
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING {returning}"
    else:
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    ids = []
    for row in rows:
        cur.execute(sql, row)
        if returning:
            ids.append(cur.fetchone()[0])
    return ids


def build_reference_data(rng: random.Random, cfg: Dict[str, int]):
    roles = [(name, psycopg2.extras.Json({
        "Администратор": {"all": True},
        "ПТО": {"planning": True, "reports": True},
        "МТС": {"materials": True, "deliveries": True},
        "Руководитель": {"dashboard": True, "approvals": True},
    }[name])) for name in ROLE_NAMES]

    users = []
    for i in range(cfg["users"]):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        pat = rng.choice(PATRONYMICS)
        login = f"{last.lower()}.{first.lower()}{i+1}"
        role = rng.choice(ROLE_NAMES)
        users.append((login, f"{last} {first} {pat}", role))

    objects = []
    base = date.today() - timedelta(days=500)
    for i in range(cfg["objects"]):
        t = rng.choice(OBJECT_TYPES)
        ps = base + timedelta(days=rng.randint(0, 250))
        pf = ps + timedelta(days=rng.randint(120, 540))
        if rng.random() < 0.2:
            pf = None
        objects.append((
            f"Объект {i+1}: {t}",
            f"г. Тюмень, ул. Строителей, {rng.randint(1, 250)}",
            t,
            ps,
            pf,
            round(rng.uniform(20_000_000, 220_000_000), 2),
            rng.choice(["ООО \"Тюмень Водоканал\"", "АО \"Горводоканал\"", "МУП \"Водоканал\"", "Департамент строительства"]),
        ))

    work_types = []
    for i in range(cfg["work_types"]):
        work_types.append((
            f"{rng.choice(WORK_GROUPS)} {i+1}",
            rng.choice(["м", "м2", "м3", "шт", "т", "компл"]),
            round(rng.uniform(0.05, 4.5), 3),
            rng.choice(WORK_GROUPS),
        ))

    materials = []
    material_prefixes = ["Труба", "Клапан", "Муфта", "Кабель", "Бетон", "Щебень", "Арматура", "Химреагент", "Смесь", "Плита"]
    for i in range(cfg["materials"]):
        materials.append((
            f"{rng.choice(material_prefixes)} {i+1}",
            rng.choice(["шт", "м", "кг", "т", "л"]),
            round(rng.uniform(0.2, 12.0), 4),
            rng.choice(MATERIAL_CATEGORIES),
            rng.random() < 0.6,
        ))

    suppliers = []
    for i in range(cfg["suppliers"]):
        inn = f"{100000000000 + i:012d}"
        suppliers.append((
            f"{rng.choice(['СтройПоставка', 'ТехноМир', 'СнабСервис', 'РегионКомплект', 'ВодСтрой'])} {i+1}",
            inn,
            rng.choice(SUPPLIER_CLASSES),
        ))

    warehouses = []
    for i in range(cfg["warehouses"]):
        warehouses.append((
            f"Склад {i+1}",
            f"г. Тюмень, складская зона {i+1}",
            round(rng.uniform(500, 5000), 2),
            rng.randint(1, 4),
            round(rng.uniform(1.0, 8.0), 4),
            rng.randint(30, 240),
        ))

    brigades = []
    for i in range(cfg["brigades"]):
        brigades.append((f"Бригада {i+1}", rng.randint(4, 14), rng.choice(["Тюмень", "Тобольск", "Ишим", "Ялуторовск"])))

    qualifications = [(f"Квалификация {i+1}", rng.randint(1, 10)) for i in range(cfg["qualifications"])]

    equipment = []
    for i in range(cfg["equipment"]):
        equipment.append((
            rng.choice(EQUIPMENT_TYPES),
            f"{rng.choice(['X', 'M', 'PRO', 'MAX'])}-{rng.randint(100, 999)}",
            rng.randint(1, cfg["warehouses"]),
            weighted_choice(rng, ["available", "in_use", "maintenance", "broken"], [6, 2, 1, 1]),
        ))

    return roles, users, objects, work_types, materials, suppliers, warehouses, brigades, qualifications, equipment


def build_sites(rng: random.Random, object_ids: List[int], cfg: Dict[str, int]):
    rows = []
    sites_by_object: Dict[int, List[int]] = defaultdict(list)
    for oid in object_ids:
        n = rng.randint(cfg["sites_per_object_min"], cfg["sites_per_object_max"])
        for i in range(n):
            rows.append((oid, f"Участок {oid}-{i+1}", f"({round(rng.uniform(30,60),6)},{round(rng.uniform(50,80),6)})", round(rng.uniform(50, 2500), 3)))
    return rows


def build_consumption_norms(rng: random.Random, work_type_ids: List[int], material_ids: List[int]):
    rows = []
    for wt in work_type_ids:
        for mid in rng.sample(material_ids, rng.randint(3, min(8, len(material_ids)))):
            rows.append((wt, mid, round(rng.uniform(0.01, 8.0), 6), date.today() - timedelta(days=rng.randint(0, 730))))
    return rows


def build_supply_contracts(rng: random.Random, supplier_ids: List[int], material_ids: List[int]):
    rows = []
    for sid in supplier_ids:
        for mid in rng.sample(material_ids, rng.randint(2, min(7, len(material_ids)))):
            start = date.today() - timedelta(days=rng.randint(90, 500))
            valid_to = start + timedelta(days=rng.randint(180, 720))
            rows.append((sid, mid, round(rng.uniform(50, 9500), 2), rng.randint(1, 35), round(rng.uniform(50, 1500), 3), start, valid_to if rng.random() > 0.15 else None))
    return rows


def build_transport_params(rng: random.Random, material_ids: List[int], warehouse_ids: List[int]):
    rows = []
    for mid in material_ids:
        for wid in rng.sample(warehouse_ids, rng.randint(1, len(warehouse_ids))):
            rows.append((mid, wid, round(rng.uniform(1, 80), 3), rng.randint(1, 14)))
    return rows


def calc_schedule(works: List[dict]):
    es, ef = {}, {}
    for w in works:
        preds = w["preds"]
        start = max((ef[p] for p in preds), default=0)
        es[w["work_id"]] = start
        ef[w["work_id"]] = start + w["duration"]

    t_min = max(ef.values()) if ef else 0
    successors: Dict[int, List[int]] = defaultdict(list)
    for w in works:
        for p in w["preds"]:
            successors[p].append(w["work_id"])

    ls, lf = {}, {}
    for w in reversed(works):
        succ = successors.get(w["work_id"], [])
        lf[w["work_id"]] = min((ls[s] for s in succ), default=t_min)
        ls[w["work_id"]] = lf[w["work_id"]] - w["duration"]

    items = []
    for w in works:
        tf = ls[w["work_id"]] - es[w["work_id"]]
        items.append((w["work_id"], es[w["work_id"]], ef[w["work_id"]], ls[w["work_id"]], lf[w["work_id"]], tf, tf == 0))
    return t_min, items, es, ef


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--truncate", action="store_true")
    ap.add_argument("--projects", type=int, default=6, help="Сколько объектов использовать для проектов")
    ap.add_argument("--skip-scenario-actions", action="store_true", help="Не пытаться заполнять risk.scenario_action")
    args = ap.parse_args()

    cfg = DEFAULTS.copy()
    rng = random.Random(args.seed)

    conn = connect(args.dsn)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            if args.truncate:
                truncate_all(cur)

            # --------------------
            # REF
            # --------------------
            roles, users, objects, work_types, materials, suppliers, warehouses, brigades, qualifications, equipment = build_reference_data(rng, cfg)

            insert_many(cur, "ref.role", ["name", "permissions"], roles)
            role_to_id = {}
            cur.execute("SELECT role_id, name FROM ref.role")
            for rid, name in cur.fetchall():
                role_to_id[name] = rid

            insert_many(cur, "ref.app_user", ["login", "full_name", "role_id", "is_active"], [(login, full_name, role_to_id[role], True) for login, full_name, role in users])
            insert_many(cur, "ref.object", ["name", "address", "type", "planned_start", "planned_finish", "contract_amount", "customer"], objects)
            cur.execute("SELECT object_id FROM ref.object ORDER BY object_id")
            object_ids = [r[0] for r in cur.fetchall()]

            site_rows = build_sites(rng, object_ids, cfg)
            insert_many(cur, "ref.site", ["object_id", "name", "coordinates", "planned_volume"], site_rows)
            cur.execute("SELECT site_id, object_id FROM ref.site ORDER BY site_id")
            site_pairs = cur.fetchall()
            sites_by_object: Dict[int, List[int]] = defaultdict(list)
            for sid, oid in site_pairs:
                sites_by_object[oid].append(sid)

            insert_many(cur, "ref.work_type", ["name", "unit", "normative_productivity", "technological_group"], work_types)
            cur.execute("SELECT work_type_id FROM ref.work_type ORDER BY work_type_id")
            work_type_ids = [r[0] for r in cur.fetchall()]

            insert_many(cur, "ref.material", ["name", "unit", "storage_coefficient", "category", "requires_certification"], materials)
            cur.execute("SELECT material_id FROM ref.material ORDER BY material_id")
            material_ids = [r[0] for r in cur.fetchall()]

            insert_many(cur, "ref.supplier", ["name", "inn", "reliability_class"], suppliers)
            cur.execute("SELECT supplier_id FROM ref.supplier ORDER BY supplier_id")
            supplier_ids = [r[0] for r in cur.fetchall()]

            insert_many(cur, "ref.warehouse", ["name", "address", "capacity", "loading_posts", "service_rate", "allowed_wait_time"], warehouses)
            cur.execute("SELECT warehouse_id FROM ref.warehouse ORDER BY warehouse_id")
            warehouse_ids = [r[0] for r in cur.fetchall()]

            insert_many(cur, "ref.brigade", ["name", "headcount", "base_location"], brigades)
            cur.execute("SELECT brigade_id FROM ref.brigade ORDER BY brigade_id")
            brigade_ids = [r[0] for r in cur.fetchall()]

            insert_many(cur, "ref.qualification", ["name", "level"], qualifications)
            cur.execute("SELECT qualification_id FROM ref.qualification ORDER BY qualification_id")
            qualification_ids = [r[0] for r in cur.fetchall()]

            insert_many(cur, "ref.equipment", ["type", "model", "base_warehouse_id", "availability_status"], equipment)
            cur.execute("SELECT equipment_id FROM ref.equipment ORDER BY equipment_id")
            equipment_ids = [r[0] for r in cur.fetchall()]

            # --------------------
            # NORM
            # --------------------
            insert_many(cur, "norm.consumption_norm", ["work_type_id", "material_id", "norm_value", "effective_from"], build_consumption_norms(rng, work_type_ids, material_ids))
            insert_many(cur, "norm.brigade_qualification", ["brigade_id", "qualification_id"], [(bid, qid) for bid in brigade_ids for qid in rng.sample(qualification_ids, rng.randint(1, min(3, len(qualification_ids))))])
            insert_many(cur, "norm.supply_contract", ["supplier_id", "material_id", "price_per_unit", "min_delivery_days", "max_volume_per_period", "valid_from", "valid_to"], build_supply_contracts(rng, supplier_ids, material_ids))
            insert_many(cur, "norm.transport_param", ["material_id", "warehouse_id", "avg_capacity", "avg_delivery_time"], build_transport_params(rng, material_ids, warehouse_ids))

            cur.execute("SELECT supplier_id, material_id, price_per_unit FROM norm.supply_contract")
            contract_prices = {(sid, mid): float(price) for sid, mid, price in cur.fetchall()}

            # --------------------
            # SRO: projects / works / schedule
            # --------------------
            used_object_ids = object_ids[: max(1, min(args.projects, len(object_ids)))]
            project_rows = []
            project_meta = []
            for oid in used_object_ids:
                n_projects = rng.randint(cfg["projects_per_object_min"], cfg["projects_per_object_max"])
                for _ in range(n_projects):
                    ps = date.today() - timedelta(days=rng.randint(90, 420))
                    pf = ps + timedelta(days=rng.randint(120, 420))
                    status = weighted_choice(rng, ["planned", "in_progress", "completed", "suspended", "cancelled"], [1.5, 2.5, 2.0, 0.5, 0.2])
                    actual_start = ps + timedelta(days=rng.randint(0, 15)) if status in {"in_progress", "completed", "suspended"} else None
                    actual_finish = pf if status == "completed" else None
                    project_rows.append((oid, status, ps, pf, actual_start, actual_finish))
                    project_meta.append((oid, ps, pf, status))

            insert_many(cur, "sro.project", ["object_id", "status", "plan_start", "plan_finish", "actual_start", "actual_finish"], project_rows)
            cur.execute("SELECT project_id, object_id, plan_start, plan_finish, status FROM sro.project ORDER BY project_id")
            projects = cur.fetchall()

            project_works: Dict[int, List[dict]] = {}
            project_calc_id: Dict[int, int] = {}

            for (project_id, object_id, plan_start, plan_finish, status) in projects:
                n_works = rng.randint(cfg["works_per_project_min"], cfg["works_per_project_max"])
                available_sites = sites_by_object.get(object_id, object_ids and [site_pairs[0][0]] or [])
                works = []
                work_insert_rows = []
                for i in range(n_works):
                    site_id = rng.choice(available_sites)
                    work_type_id = rng.choice(work_type_ids)
                    duration = rng.randint(1, 20)
                    volume = round(rng.uniform(10, 1500), 3)
                    req_qual = rng.choice(qualification_ids) if rng.random() < 0.7 else None
                    req_eq = rng.choice(EQUIPMENT_TYPES) if rng.random() < 0.55 else None
                    work_insert_rows.append((project_id, site_id, work_type_id, duration, volume, req_qual, req_eq))

                insert_many(cur, "sro.work", ["project_id", "site_id", "work_type_id", "duration", "volume", "required_qualification_id", "required_equipment_type"], work_insert_rows)
                cur.execute("SELECT work_id FROM sro.work WHERE project_id = %s ORDER BY work_id", (project_id,))
                work_ids = [r[0] for r in cur.fetchall()]

                for idx, wid in enumerate(work_ids):
                    preds = rng.sample(work_ids[:idx], rng.randint(0, min(3, idx))) if idx else []
                    works.append({
                        "work_id": wid,
                        "project_id": project_id,
                        "site_id": work_insert_rows[idx][1],
                        "work_type_id": work_insert_rows[idx][2],
                        "duration": work_insert_rows[idx][3],
                        "volume": work_insert_rows[idx][4],
                        "preds": preds,
                    })

                project_works[project_id] = works
                for w in works:
                    for p in w["preds"]:
                        cur.execute("INSERT INTO sro.work_predecessor (work_id, predecessor_work_id) VALUES (%s, %s)", (w["work_id"], p))

                t_min, schedule_items, es_map, ef_map = calc_schedule(works)
                cur.execute(
                    "INSERT INTO sro.schedule_calculation (project_id, calculation_date, version, t_min, scenario) VALUES (%s, %s, %s, %s, %s) RETURNING calculation_id",
                    (project_id, datetime.now(), 1, t_min, "plan"),
                )
                calc_id = cur.fetchone()[0]
                project_calc_id[project_id] = calc_id

                for wid, es, ef, ls, lf, tf, critical in schedule_items:
                    cur.execute(
                        """
                        INSERT INTO sro.schedule_item
                          (calculation_id, work_id, es, ef, ls, lf, tf, is_critical)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (calc_id, wid, es, ef, ls, lf, tf, critical),
                    )

                # brigades / equipment
                for _ in range(rng.randint(1, 3)):
                    cur.execute(
                        """
                        INSERT INTO sro.brigade_assignment
                          (brigade_id, site_id, period_start, period_end, assignment_cost, schedule_calculation_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            rng.choice(brigade_ids),
                            rng.choice(available_sites),
                            plan_start + timedelta(days=rng.randint(0, max(1, (plan_finish - plan_start).days // 2))),
                            plan_start + timedelta(days=rng.randint(max(1, (plan_finish - plan_start).days // 2), max(2, (plan_finish - plan_start).days))),
                            round(rng.uniform(50_000, 500_000), 4),
                            calc_id,
                        ),
                    )

                for eq in rng.sample(equipment_ids, rng.randint(1, min(4, len(equipment_ids)))):
                    s = plan_start + timedelta(days=rng.randint(0, max(1, (plan_finish - plan_start).days // 2)))
                    e = min(plan_finish, s + timedelta(days=rng.randint(5, 40)))
                    cur.execute(
                        "INSERT INTO sro.equipment_assignment (equipment_id, site_id, period_start, period_end) VALUES (%s, %s, %s, %s)",
                        (eq, rng.choice(available_sites), s, e),
                    )

                # demand derived from norms
                cur.execute("SELECT work_type_id, material_id, norm_value FROM norm.consumption_norm WHERE work_type_id = ANY(%s)", (work_type_ids,))
                norm_map: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
                for wt, mid, nv in cur.fetchall():
                    norm_map[wt].append((mid, float(nv)))

                demand_agg = defaultdict(float)
                for w in works:
                    for mid, nv in rng.sample(norm_map[w["work_type_id"]], min(len(norm_map[w["work_type_id"]]), rng.randint(1, 4))):
                        d = plan_start + timedelta(days=es_map[w["work_id"]] + rng.randint(0, 14))
                        demand_agg[(project_id, mid, d, calc_id)] += round(w["volume"] * nv * rng.uniform(0.7, 1.3), 3)
                for (pid, mid, d, cid), qty in demand_agg.items():
                    cur.execute(
                        """
                        INSERT INTO mtr.material_demand
                          (project_id, material_id, demand_date, quantity, schedule_calculation_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (project_id, material_id, demand_date, schedule_calculation_id)
                        DO UPDATE SET quantity = mtr.material_demand.quantity + EXCLUDED.quantity
                        """,
                        (pid, mid, d, round(qty, 3), cid),
                    )

                # work execution / risk params / deviations
                for w in works:
                    start = plan_start + timedelta(days=es_map[w["work_id"]])
                    end = plan_start + timedelta(days=ef_map[w["work_id"]])

                    remaining = w["volume"]
                    n_exec = rng.randint(cfg["executions_per_work_min"], cfg["executions_per_work_max"])
                    for j in range(n_exec):
                        ex_date = start + timedelta(days=min(j * max(1, w["duration"] // n_exec), max(0, w["duration"] - 1)))
                        if j == n_exec - 1:
                            fact_volume = max(0.0, round(remaining, 3))
                        else:
                            fact_volume = round(w["volume"] * rng.uniform(0.1, 0.5) / n_exec, 3)
                            remaining -= fact_volume
                        fact_percent = round(min(1.0, max(0.0, fact_volume / w["volume"])), 4)
                        cur.execute(
                            """
                            INSERT INTO ops.work_execution
                              (work_id, execution_date, fact_volume, fact_percent, responsible_user_id, comments)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (w["work_id"], ex_date, fact_volume, fact_percent, rng.randint(1, cfg["users"]), rng.choice(["Выполнено без замечаний", "Есть замечания по качеству", "Требуется уточнение объёма", None])),
                        )

                    optimistic = round(w["duration"] * rng.uniform(0.6, 0.85), 3)
                    most_likely = round(w["duration"] * rng.uniform(0.9, 1.15), 3)
                    pessimistic = round(w["duration"] * rng.uniform(1.2, 1.8), 3)
                    optimistic, most_likely, pessimistic = sorted([optimistic, most_likely, pessimistic])
                    alpha = round(1 + 4 * (most_likely - optimistic) / max(pessimistic - optimistic, 0.001), 4)
                    beta = round(1 + 4 * (pessimistic - most_likely) / max(pessimistic - optimistic, 0.001), 4)
                    expected_duration = round((optimistic + 4 * most_likely + pessimistic) / 6, 3)
                    std_deviation = round((pessimistic - optimistic) / 6, 3)
                    cur.execute(
                        """
                        INSERT INTO risk.work_risk_params
                          (work_id, optimistic, most_likely, pessimistic, alpha, beta, expected_duration, std_deviation)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (work_id)
                        DO UPDATE SET
                            optimistic = EXCLUDED.optimistic,
                            most_likely = EXCLUDED.most_likely,
                            pessimistic = EXCLUDED.pessimistic,
                            alpha = EXCLUDED.alpha,
                            beta = EXCLUDED.beta,
                            expected_duration = EXCLUDED.expected_duration,
                            std_deviation = EXCLUDED.std_deviation
                        """,
                        (w["work_id"], optimistic, most_likely, pessimistic, alpha, beta, expected_duration, std_deviation),
                    )

                    if rng.random() < 0.2:
                        plan_p = round(rng.uniform(0.2, 0.95), 4)
                        fact_p = round(min(1.0, max(0.0, plan_p + rng.uniform(-0.35, 0.2))), 4)
                        delta_p = round(fact_p - plan_p, 4)
                        category = rng.choice(DEVIATION_CATEGORIES)
                        chi_mtr = category == "MTR" or rng.random() < 0.3
                        cur.execute(
                            """
                            INSERT INTO ops.deviation
                              (work_id, detection_date, plan_percent, fact_percent, delta_percent, chi_mtr, category)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING deviation_id
                            """,
                            (w["work_id"], end, plan_p, fact_p, delta_p, chi_mtr, category),
                        )
                        dev_id = cur.fetchone()[0]
                        if chi_mtr:
                            for _ in range(rng.randint(1, 2)):
                                cur.execute(
                                    """
                                    INSERT INTO ops.deviation_cause
                                      (deviation_id, material_id, supplier_id, deficit_days, deficit_volume)
                                    VALUES (%s, %s, %s, %s, %s)
                                    """,
                                    (dev_id, rng.choice(material_ids), rng.choice(supplier_ids), rng.randint(1, 18), round(rng.uniform(5, 120), 3)),
                                )

                # stock balances / movements / load profile
                for wid in warehouse_ids:
                    for mid in rng.sample(material_ids, rng.randint(5, min(10, len(material_ids)))):
                        bdate = plan_start + timedelta(days=rng.randint(-20, 20))
                        qty = round(rng.uniform(0, 1200), 3)
                        reserved = round(rng.uniform(0, min(qty, 300)), 3)
                        cur.execute(
                            """
                            INSERT INTO mtr.stock_balance
                              (material_id, warehouse_id, balance_date, quantity, reserved_quantity)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (material_id, warehouse_id, balance_date)
                            DO UPDATE SET quantity = EXCLUDED.quantity,
                                          reserved_quantity = EXCLUDED.reserved_quantity
                            """,
                            (mid, wid, bdate, qty, reserved),
                        )
                        for _ in range(2):
                            mdt = datetime.combine(bdate, datetime.min.time()) + timedelta(days=rng.randint(-10, 20), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
                            cur.execute(
                                """
                                INSERT INTO mtr.stock_movement
                                  (material_id, warehouse_id, movement_date, movement_type, quantity, source_document_id, source_document_type)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (mid, wid, mdt, rng.choice(["incoming", "outgoing", "transfer", "writeoff"]), round(rng.uniform(1, 400), 3), None, None),
                            )

                for wid in rng.sample(warehouse_ids, rng.randint(2, len(warehouse_ids))):
                    for dd in range(rng.randint(10, 20)):
                        d = plan_start + timedelta(days=dd)
                        total_load = round(rng.uniform(0, 1000), 2)
                        cur.execute(
                            """
                            INSERT INTO mtr.warehouse_load_profile
                              (warehouse_id, profile_date, total_load, peak_indicator, queue_length, wait_time)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (warehouse_id, profile_date)
                            DO UPDATE SET total_load = EXCLUDED.total_load,
                                          peak_indicator = EXCLUDED.peak_indicator,
                                          queue_length = EXCLUDED.queue_length,
                                          wait_time = EXCLUDED.wait_time
                            """,
                            (wid, d, total_load, total_load > 800, round(rng.uniform(0, 12), 3), round(rng.uniform(0, 240), 3)),
                        )

                # deliveries
                for _ in range(rng.randint(cfg["deliveries_per_project_min"], cfg["deliveries_per_project_max"])):
                    mid = rng.choice(material_ids)
                    wid = rng.choice(warehouse_ids)
                    sid = rng.choice(supplier_ids)
                    planned_date = plan_start + timedelta(days=rng.randint(0, max(1, (plan_finish - plan_start).days)))
                    planned_volume = round(rng.uniform(5, 300), 3)
                    unit_cost = round(contract_prices.get((sid, mid), rng.uniform(80, 8000)), 2)
                    status = weighted_choice(rng, DELIVERY_STATUSES, [2.0, 2.0, 1.5, 2.5, 0.3])
                    cur.execute(
                        """
                        INSERT INTO mtr.planned_delivery
                          (project_id, material_id, warehouse_id, supplier_id, planned_date, planned_volume, unit_cost, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING planned_delivery_id
                        """,
                        (project_id, mid, wid, sid, planned_date, planned_volume, unit_cost, status),
                    )
                    pd_id = cur.fetchone()[0]
                    if status in ("shipped", "delivered"):
                        actual_date = planned_date + timedelta(days=rng.randint(-2, 12))
                        actual_volume = round(planned_volume * rng.uniform(0.9, 1.1), 3)
                        cur.execute(
                            """
                            INSERT INTO mtr.actual_delivery
                              (planned_delivery_id, material_id, warehouse_id, supplier_id, actual_date, actual_volume, deviation_days)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (pd_id, mid, wid, sid, actual_date, actual_volume, (actual_date - planned_date).days),
                        )

                # availability dates
                for mid in rng.sample(material_ids, rng.randint(3, min(8, len(material_ids)))):
                    avail = plan_start + timedelta(days=rng.randint(0, max(1, (plan_finish - plan_start).days)))
                    cur.execute(
                        """
                        INSERT INTO mtr.material_availability_date
                          (project_id, material_id, availability_date, calculation_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (project_id, material_id, calculation_id)
                        DO UPDATE SET availability_date = EXCLUDED.availability_date
                        """,
                        (project_id, mid, avail, calc_id),
                    )

                # KS-2 / KS-3
                for act_no in range(1, rng.randint(1, 3) + 1):
                    act_date = plan_start + timedelta(days=rng.randint(10, max(15, (plan_finish - plan_start).days)))
                    act_number = f"КС2-{project_id}-{act_no}"
                    signed_status = weighted_choice(rng, ACT_STATUSES, [2.0, 1.7, 1.2, 0.2])
                    cur.execute(
                        """
                        INSERT INTO ops.ks2_act
                          (project_id, act_number, act_date, total_amount, signed_status, electronic_signature_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING act_id
                        """,
                        (project_id, act_number, act_date, 0.0, signed_status, None),
                    )
                    act_id = cur.fetchone()[0]
                    subset = rng.sample(work_ids, rng.randint(2, min(6, len(work_ids))))
                    subtotal = 0.0
                    for wid in subset:
                        accepted_volume = round(rng.uniform(1, 120), 3)
                        unit_price = round(rng.uniform(500, 25000), 2)
                        total = round(accepted_volume * unit_price, 2)
                        subtotal += total
                        cur.execute(
                            "INSERT INTO ops.ks2_item (act_id, work_id, accepted_volume, unit_price, total) VALUES (%s, %s, %s, %s, %s)",
                            (act_id, wid, accepted_volume, unit_price, total),
                        )
                    cur.execute("UPDATE ops.ks2_act SET total_amount = %s WHERE act_id = %s", (round(subtotal, 2), act_id))
                    cur.execute(
                        "INSERT INTO ops.ks3_certificate (project_id, period_start, period_end, total_amount) VALUES (%s, %s, %s, %s)",
                        (project_id, act_date - timedelta(days=30), act_date, round(subtotal * rng.uniform(0.8, 1.2), 2)),
                    )

                # supplier stats
                for sid in rng.sample(supplier_ids, rng.randint(2, min(5, len(supplier_ids)))):
                    for mid in rng.sample(material_ids, rng.randint(2, min(6, len(material_ids)))):
                        cur.execute(
                            """
                            INSERT INTO risk.supplier_delivery_stats
                              (supplier_id, material_id, mu_log, sigma_log, sample_size, last_updated)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (supplier_id, material_id)
                            DO UPDATE SET mu_log = EXCLUDED.mu_log,
                                          sigma_log = EXCLUDED.sigma_log,
                                          sample_size = EXCLUDED.sample_size,
                                          last_updated = EXCLUDED.last_updated
                            """,
                            (sid, mid, round(rng.uniform(0.5, 3.5), 4), round(rng.uniform(0.1, 0.9), 4), rng.randint(20, 400), datetime.now()),
                        )

                # Monte-Carlo
                cur.execute("SELECT t_min FROM sro.schedule_calculation WHERE calculation_id = %s", (calc_id,))
                t_min = cur.fetchone()[0] or 1
                iterations = cfg["monte_carlo_iterations"]
                seed = rng.randint(1, 2**31 - 1)
                rng_mc = random.Random(seed)
                t_values = []
                cur.execute(
                    """
                    INSERT INTO risk.monte_carlo_run
                      (project_id, run_date, iterations_count, seed, mean_duration, std_duration, prob_on_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING run_id
                    """,
                    (project_id, datetime.now(), iterations, seed, 0, 0, 0),
                )
                run_id = cur.fetchone()[0]
                iter_rows = []
                for i in range(1, iterations + 1):
                    t_r = max(1.0, rng_mc.gauss(t_min * 1.08, max(t_min * 0.12, 1.0)))
                    c_r = round(t_r * rng_mc.uniform(15000, 65000), 2)
                    t_values.append(t_r)
                    iter_rows.append((run_id, i, round(t_r, 3), c_r))
                insert_many(cur, "risk.monte_carlo_iteration", ["run_id", "iteration_number", "t_r", "c_r"], iter_rows)
                mean_duration = round(statistics.mean(t_values), 3)
                std_duration = round(statistics.pstdev(t_values), 3)
                prob_on_time = round(sum(1 for x in t_values if x <= t_min) / len(t_values), 4)
                cur.execute(
                    "UPDATE risk.monte_carlo_run SET mean_duration = %s, std_duration = %s, prob_on_time = %s WHERE run_id = %s",
                    (mean_duration, std_duration, prob_on_time, run_id),
                )
                for gamma in (0.5, 0.8, 0.95):
                    sorted_vals = sorted(t_values)
                    idx = min(len(sorted_vals) - 1, max(0, int(round(gamma * len(sorted_vals) + 0.0001)) - 1))
                    cur.execute("INSERT INTO risk.risk_quantile (run_id, gamma_level, t_gamma) VALUES (%s, %s, %s)", (run_id, gamma, round(sorted_vals[idx], 3)))
                for w in works:
                    criticality_index = 1.0 if len(w["preds"]) == 0 else round(max(0.0, 1.0 - len(w["preds"]) * 0.25 + rng.random() * 0.2), 4)
                    cur.execute(
                        "INSERT INTO risk.work_criticality_index (run_id, work_id, criticality_index, risk_critical) VALUES (%s, %s, %s, %s)",
                        (run_id, w["work_id"], criticality_index, criticality_index >= 0.6),
                    )

                # correction scenarios
                cur.execute("SELECT deviation_id FROM ops.deviation WHERE work_id IN (SELECT work_id FROM sro.work WHERE project_id = %s) ORDER BY deviation_id DESC LIMIT 1", (project_id,))
                dev = cur.fetchone()
                if dev:
                    dev_id = dev[0]
                    cur.execute(
                        """
                        INSERT INTO risk.correction_scenario
                          (deviation_id, generation_date, description, delta_t, delta_c, delta_r, j_score, is_recommended)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING scenario_id
                        """,
                        (
                            dev_id,
                            datetime.now(),
                            rng.choice([
                                "Ускорение поставки по критичному материалу",
                                "Перераспределение бригад между участками",
                                "Параллелизация работ на смежных фронтах",
                                "Привлечение дополнительной техники",
                            ]),
                            round(rng.uniform(-12, -1), 3),
                            round(rng.uniform(50_000, 400_000), 2),
                            round(rng.uniform(-0.3, 0.2), 4),
                            round(rng.uniform(0.1, 0.99), 4),
                            rng.random() < 0.4,
                        ),
                    )
                    scenario_id = cur.fetchone()[0]

                    # scenario_action в текущем DDL лучше не трогать: там PK задан через COALESCE,
                    # что PostgreSQL не принимает. Если DDL будет исправлен, блок можно вернуть.
                    if not args.skip_scenario_actions:
                        cur.execute("SELECT to_regclass('risk.scenario_action')")
                        if cur.fetchone()[0] is not None:
                            pass

            conn.commit()
            print("Загрузка завершена успешно.")
            print(f"Объектов: {len(object_ids)}")
            print(f"Проектов: {len(projects)}")

    except Exception as exc:
        conn.rollback()
        raise SystemExit(f"Ошибка загрузки: {exc}") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
