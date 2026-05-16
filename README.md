# АС управления строительными работами и МТР
### REST API серверной части (ВКР Чучалина А.И.)

---

## Стек

- **Python 3.9+**
- **FastAPI** — веб-фреймворк
- **SQLAlchemy 2.0** (async) — ORM
- **PostgreSQL** — база данных
- **python-jose** — JWT авторизация
- **passlib[bcrypt]** — хэширование паролей
- **Uvicorn** — ASGI-сервер

---

## Структура проекта

```
app/
├── api/
│   └── v1/
│       ├── endpoints/       # Роуты (auth, users, projects, works, ...)
│       └── router.py        # Подключение всех роутеров
├── core/
│   ├── config.py            # Настройки приложения (.env)
│   ├── security.py          # JWT и хэширование паролей
│   └── exceptions.py        # Обработчики ошибок
├── db/
│   ├── base.py              # Импорт всех моделей для create_all
│   ├── base_class.py        # Базовый класс SQLAlchemy
│   └── session.py           # Движок и фабрика сессий
├── models/                  # SQLAlchemy-модели (таблицы БД)
│   ├── user.py
│   ├── sro.py
│   └── ref_object.py
├── schemas/                 # Pydantic-схемы (запросы/ответы)
│   ├── auth.py
│   └── schedule.py
└── main.py                  # Точка входа
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

Приложение будет доступно по адресу: [http://localhost:8000](http://localhost:8000)

---

## Документация API

| URL | Описание |
|---|---|
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |
| `/health` | Статус сервера |

---

## Основные эндпоинты

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Получить токен |
| `POST` | `/api/v1/auth/refresh` | Обновить токен |
| `POST` | `/api/v1/auth/logout` | Выйти |
| `GET` | `/api/v1/users/me` | Текущий пользователь |
| `GET` | `/api/v1/projects` | Список проектов |
| `GET` | `/api/v1/works` | Список работ |
| `GET` | `/api/v1/schedule` | Календарное планирование |
| `GET` | `/api/v1/reports` | Отчётность |
