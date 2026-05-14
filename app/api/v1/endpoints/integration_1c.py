from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SyncRequest(BaseModel):
    project_id: int
    direction: str = "pull"


class ContractorOut(BaseModel):
    id: str
    name: str
    inn: str
    contact: str


class InvoiceOut(BaseModel):
    id: str
    project_id: int
    supplier: str
    amount: float
    currency: str
    status: str


@router.post("/sync", summary="Синхронизировать данные с 1С:Предприятие")
async def sync_with_1c(body: SyncRequest):
    return {
        "detail": "Синхронизация выполнена (заглушка)",
        "project_id": body.project_id,
        "direction": body.direction,
        "synced_records": 0,
    }


@router.get("/contractors", response_model=List[ContractorOut], summary="Справочник контрагентов из 1С")
async def get_contractors():
    return [ContractorOut(id="1C-001", name="ООО СтройМатериалы", inn="7200123456", contact="info@stroymaterials.ru")]


@router.get("/invoices", response_model=List[InvoiceOut], summary="Счета-фактуры из 1С")
async def get_invoices(project_id: Optional[int] = None):
    return [InvoiceOut(id="INV-0001", project_id=project_id or 1, supplier="ООО СтройМатериалы", amount=250000.0, currency="RUB", status="paid")]


@router.get("/status", summary="Статус подключения к 1С")
async def get_1c_status():
    return {"connected": False, "detail": "Заглушка — интеграция не настроена", "version": "1С:Предприятие 8.3"}
