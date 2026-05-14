from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, projects, works, schedule, materials,
    supply, risks, control, reports, integration_1c, ws,
)

api_router = APIRouter()
api_router.include_router(auth.router,           prefix="/auth",        tags=["Авторизация"])
api_router.include_router(users.router,          prefix="/users",       tags=["Пользователи"])
api_router.include_router(projects.router,       prefix="/projects",    tags=["Проекты"])
api_router.include_router(works.router,          prefix="/works",       tags=["Работы"])
api_router.include_router(schedule.router,       prefix="/schedule",    tags=["Календарное планирование"])
api_router.include_router(materials.router,      prefix="/materials",   tags=["Справочник материалов"])
api_router.include_router(supply.router,         prefix="/supply",      tags=["МТО"])
api_router.include_router(risks.router,          prefix="/risks",       tags=["Анализ рисков"])
api_router.include_router(control.router,        prefix="/control",     tags=["Оперативный контроль"])
api_router.include_router(reports.router,        prefix="/reports",     tags=["Отчётность"])
api_router.include_router(integration_1c.router, prefix="/integration", tags=["Интеграция с 1С"])
api_router.include_router(ws.router,             prefix="/ws",          tags=["WebSocket"])