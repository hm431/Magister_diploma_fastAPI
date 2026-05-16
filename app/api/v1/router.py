from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.api.v1.endpoints import (
    auth, users, projects, works, schedule, materials,
    supply, risks, control, reports, integration_1c, ws,
    brigade_assignment,
)

api_router = APIRouter()

# Авторизация — открытый доступ
api_router.include_router(auth.router,           prefix="/auth",        tags=["Авторизация"])

# Все остальные роуты закрыты — требуют валидный Bearer токен
protected = {"dependencies": [Depends(get_current_user)]}

api_router.include_router(users.router,          prefix="/users",       tags=["Пользователи"],               **protected)
api_router.include_router(projects.router,       prefix="/projects",    tags=["Проекты"],                    **protected)
api_router.include_router(works.router,          prefix="/works",       tags=["Работы"],                     **protected)
api_router.include_router(schedule.router,       prefix="/schedule",    tags=["Календарное планирование"],   **protected)
api_router.include_router(materials.router,      prefix="/materials",   tags=["Справочник материалов"],      **protected)
api_router.include_router(supply.router,         prefix="/supply",      tags=["МТО"],                        **protected)
api_router.include_router(risks.router,          prefix="/risks",       tags=["Анализ рисков"],              **protected)
api_router.include_router(control.router,        prefix="/control",     tags=["Оперативный контроль"],       **protected)
api_router.include_router(reports.router,        prefix="/reports",     tags=["Отчётность"],                 **protected)
api_router.include_router(integration_1c.router,    prefix="/integration",    tags=["Интеграция с 1С"],            **protected)
api_router.include_router(ws.router,               prefix="/ws",            tags=["WebSocket"],                  **protected)
api_router.include_router(brigade_assignment.router, prefix="/sro",          tags=["Распределение бригад"],       **protected)