from __future__ import annotations

from datetime import date
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ReportRequest(BaseModel):
    project_id: int
    date_from: date
    date_to: date
    format: str = "json"


@router.post("/schedule", summary="Отчёт по календарному графику")
async def report_schedule(body: ReportRequest):
    return {
        "report": "schedule",
        "project_id": body.project_id,
        "period": {"from": str(body.date_from), "to": str(body.date_to)},
        "data": {"total_works": 42, "completed": 15, "in_progress": 8, "planned": 19},
        "detail": "Отчёт сформирован (заглушка)",
    }


@router.post("/materials", summary="Отчёт по расходу материалов")
async def report_materials(body: ReportRequest):
    return {
        "report": "materials",
        "project_id": body.project_id,
        "period": {"from": str(body.date_from), "to": str(body.date_to)},
        "data": [{"material": "Цемент М400", "planned_qty": 200.0, "actual_qty": 185.0, "unit": "т"}],
        "detail": "Отчёт сформирован (заглушка)",
    }


@router.post("/supply", summary="Отчёт по МТО")
async def report_supply(body: ReportRequest):
    return {
        "report": "supply",
        "project_id": body.project_id,
        "period": {"from": str(body.date_from), "to": str(body.date_to)},
        "data": {"orders_total": 12, "orders_delivered": 9, "orders_pending": 3, "deficit_items": 1},
        "detail": "Отчёт сформирован (заглушка)",
    }


@router.post("/executive", summary="Сводный исполнительный отчёт")
async def report_executive(body: ReportRequest):
    return {
        "report": "executive",
        "project_id": body.project_id,
        "period": {"from": str(body.date_from), "to": str(body.date_to)},
        "kpi": {"spi": 0.85, "cpi": 0.92, "overall_progress": 35.0},
        "risks_active": 3,
        "alerts": 2,
        "detail": "Отчёт сформирован (заглушка)",
    }


@router.get("/export/{project_id}", summary="Экспорт отчёта в файл (PDF/XLSX)")
async def export_report(project_id: int, report_type: str = "executive", fmt: str = "pdf"):
    return {"detail": f"Экспорт отчёта '{report_type}' в формате {fmt} (заглушка)", "project_id": project_id, "download_url": f"/static/reports/{project_id}_{report_type}.{fmt}"}
