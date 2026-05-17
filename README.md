# АС управления строительными работами и МТР
### REST API серверной части (ВКР Чучалина А.И., МГСУ)

Система автоматизированного управления строительными проектами для ООО «Тюмень Водоканал».  
Реализует сетевое планирование (CPM), управление материально-техническими ресурсами (МТО),
анализ рисков методом Монте-Карло и оперативный контроль хода работ.

---

## Стек технологий

| Категория | Технология |
|---|---|
| Веб-фреймворк | FastAPI 0.112 + Uvicorn |
| ORM / БД | SQLAlchemy 2.0 (async) + PostgreSQL + asyncpg |
| Авторизация | JWT (python-jose) + bcrypt (passlib) |
| Математика | NumPy 1.26, SciPy 1.13, NetworkX 3.2 |
| Параллелизм | `multiprocessing.ProcessPoolExecutor` (Монте-Карло) |
| Отчётность | openpyxl, python-docx, ReportLab, Matplotlib |
| Интеграция | httpx + tenacity (1С REST) |
| WebSocket | websockets 13 |
| Логирование | Loguru |
| Тестирование | pytest + pytest-asyncio |

---

## Структура проекта

```
app/
├── api/v1/
│   ├── endpoints/
│   │   ├── auth.py             # Авторизация (JWT)
│   │   ├── users.py            # Пользователи
│   │   ├── projects.py         # Проекты
│   │   ├── works.py            # Работы (узлы сетевой модели)
│   │   ├── schedule.py         # Задача 1.1 — CPM
│   │   ├── brigade_assignment.py # Задача 1.2 — Распределение бригад
│   │   ├── mtr.py              # Задачи 2.1, 2.2 — МТО и склад
│   │   ├── risks.py            # Задача 3 — Монте-Карло
│   │   ├── ops.py              # Задача 4 — Оперативный контроль
│   │   ├── materials.py        # Справочник материалов
│   │   ├── supply.py           # Справочник поставок
│   │   ├── reports.py          # Отчётность
│   │   ├── integration_1c.py   # Интеграция с 1С
│   │   └── ws.py               # WebSocket
│   └── router.py
├── core/
│   ├── config.py               # Настройки (.env)
│   ├── security.py             # JWT и хэширование
│   └── exceptions.py           # Обработчики ошибок
├── db/
│   ├── base.py                 # Импорт всех моделей
│   ├── base_class.py           # Базовый класс SQLAlchemy
│   ├── init_db.py              # Начальные данные
│   └── session.py              # Движок и фабрика сессий
├── models/
│   ├── user.py                 # auth.user
│   ├── sro.py                  # sro.project, work, schedule_calculation, ...
│   ├── mtr.py                  # mtr.stock_balance, material_demand, ...
│   ├── norm.py                 # norm.consumption_norm, supply_contract, ...
│   ├── risk.py                 # risk.monte_carlo_run, work_criticality_index, ...
│   ├── ops.py                  # ops.deviation, deviation_cause, ...
│   ├── ref_object.py           # ref.material, warehouse, site, ...
│   └── ref_brigade.py          # ref.brigade
├── schemas/                    # Pydantic-схемы
│   ├── schedule.py
│   ├── brigade_assignment.py
│   ├── mtr.py
│   ├── risk.py
│   ├── ops.py
│   └── ...
├── services/                   # Бизнес-логика и математические модели
│   ├── cpm.py                  # Задача 1.1 — сетевой граф + CPM (формулы 2.1–2.6)
│   ├── brigade_assignment.py   # Задача 1.2 — венгерский алгоритм (2.35–2.37)
│   ├── supply_plan.py          # Задача 2.1 — LP поставок (2.8–2.18)
│   ├── warehouse_feasibility.py # Задача 2.2 — M/M/n склада (2.19–2.30)
│   ├── risk_service.py         # Задача 3 — Монте-Карло (2.39–2.50)
│   └── ops_service.py          # Задача 4 — пересчёт сроков (2.51–2.64)
└── main.py
```

---

## Схемы базы данных

```
sro   — сетевой граф: project, work, work_predecessor,
        schedule_calculation, schedule_item, brigade_assignment
mtr   — МТО: stock_balance, material_demand, planned_delivery,
        actual_delivery, material_availability_date, warehouse_load_profile
norm  — нормативы: consumption_norm, supply_contract, transport_param
risk  — риски: work_risk_params, supplier_delivery_stats,
        monte_carlo_run, monte_carlo_iteration,
        work_criticality_index, risk_quantile
ops   — оперативный контроль: work_progress, deviation,
        deviation_cause, correction_scenario
ref   — справочники: object, site, work_type, material,
        warehouse, supplier, brigade
auth  — пользователи: user
```

---

## Установка и запуск

### 1. Клонировать репозиторий

```bash
git clone <url>
cd Magister_diploma_fastAPI
```

### 2. Создать виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

Создать файл `.env` в корне проекта:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/db_name
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 5. Запустить сервер

```bash
uvicorn app.main:app --reload
```

Приложение доступно по адресу: [http://localhost:8000](http://localhost:8000)

При старте автоматически создаются все таблицы и загружаются начальные данные (`init_db`).

---

## Документация API

| URL | Описание |
|---|---|
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |
| `/health` | Статус сервера |

---

## API — реализованные задачи ВКР

### Авторизация

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Получить JWT-токен |
| `POST` | `/api/v1/auth/refresh` | Обновить токен |
| `POST` | `/api/v1/auth/logout` | Выйти |
| `GET` | `/api/v1/users/me` | Текущий пользователь |

### Задача 1.1 — Сетевая модель с ресурсными ограничениями (формулы 2.1–2.6)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/sro/schedule/{project_id}` | Расчёт CPM + ресурсные ограничения |
| `GET` | `/api/v1/sro/schedule/{project_id}/latest` | Последний расчёт графика |

Результат записывается в `sro.schedule_calculation` и `sro.schedule_item`.

### Задача 1.2 — Распределение бригад по участкам (формулы 2.35–2.37)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/sro/brigade-assignment/{calculation_id}` | Назначение бригад (венгерский алгоритм) |

Результат записывается в `sro.brigade_assignment`.

### Задача 2.1 — График поставок материалов (формулы 2.8–2.18)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/mtr/supply-plan/{project_id}/{calculation_id}` | LP-расчёт плана поставок |

Результат записывается в `mtr.material_demand`, `mtr.planned_delivery`, `mtr.material_availability_date`.

### Задача 2.2 — Загрузка склада и логистика (формулы 2.19–2.30)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/mtr/warehouse-feasibility/{project_id}/{calculation_id}` | Проверка загрузки склада (M/M/n) |

Результат записывается в `mtr.warehouse_load_profile`.

### Задача 3 — Анализ рисков Монте-Карло (формулы 2.39–2.50)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/risk/monte-carlo/{project_id}` | Имитационная оценка рисков (1000 итераций) |

Результат записывается в `risk.monte_carlo_run`, `risk.monte_carlo_iteration`, `risk.work_criticality_index`, `risk.risk_quantile`.

### Задача 4 — Оперативный контроль и пересчёт сроков (формулы 2.51–2.64)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/ops/recalculate/{project_id}` | Пересчёт по фактическим данным на дату t₀ |

Результат записывается в `ops.deviation`, `ops.deviation_cause`, `ops.correction_scenario`, `sro.schedule_calculation` (scenario='actual').

---

## Порядок вызова задач

Задачи имеют зависимости друг от друга. Рекомендуемый порядок:

```
1. POST /sro/schedule/{project_id}           ← расчёт CPM (plan)
2. POST /sro/brigade-assignment/{calc_id}    ← назначение бригад
3. POST /mtr/supply-plan/{project_id}/{calc_id}      ← план поставок + T_доступ(j)
4. POST /sro/schedule/{project_id}           ← повторный CPM с ресурсным ограничением (ф. 2.6)
5. POST /mtr/warehouse-feasibility/{project_id}/{calc_id}  ← проверка склада
6. POST /risk/monte-carlo/{project_id}       ← анализ рисков
   ─── в ходе реализации ───
7. POST /ops/recalculate/{project_id}        ← оперативный пересчёт (при отклонениях)
```

---

## Тестирование

```bash
pytest tests/ -v
```

---

## Лицензия

Проект выполнен в рамках выпускной квалификационной работы (магистратура, МГСУ, 2025).
