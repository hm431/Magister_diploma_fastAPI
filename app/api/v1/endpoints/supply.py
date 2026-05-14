from __future__ import annotations

from datetime import date
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SupplyOrderOut(BaseModel):
    id: int
    project_id: int
    material_id: int
    material_name: str
    quantity: float
    delivery_date: date
    status: str
    supplier: str


class SupplyOrderCreate(BaseModel):
    project_id: int
    material_id: int
    quantity: float
    delivery_date: date
    supplier: str


class SupplyNeedItem(BaseModel):
    material_id: int
    material_name: str
    required_quantity: float
    available_quantity: float
    deficit: float


_STUB_ORDER = SupplyOrderOut(id=1, project_id=1, material_id=1, material_name="Цемент М400", quantity=50.0, delivery_date=date(2025, 2, 1), status="pending", supplier="ООО СтройМатериалы")


@router.get("/orders", response_model=List[SupplyOrderOut], summary="Список заявок на МТО")
async def list_orders(project_id: Optional[int] = None):
    return [_STUB_ORDER]


@router.post("/orders", response_model=SupplyOrderOut, status_code=201, summary="Создать заявку на поставку")
async def create_order(body: SupplyOrderCreate):
    return SupplyOrderOut(id=2, project_id=body.project_id, material_id=body.material_id, material_name="Заглушка", quantity=body.quantity, delivery_date=body.delivery_date, status="pending", supplier=body.supplier)


@router.get("/orders/{order_id}", response_model=SupplyOrderOut, summary="Получить заявку")
async def get_order(order_id: int):
    return SupplyOrderOut(id=order_id, project_id=1, material_id=1, material_name="Цемент М400", quantity=50.0, delivery_date=date(2025, 2, 1), status="pending", supplier="ООО СтройМатериалы")


@router.patch("/orders/{order_id}/status", summary="Изменить статус заявки")
async def update_order_status(order_id: int, status: str):
    return {"order_id": order_id, "status": status, "detail": "Статус обновлён (заглушка)"}


@router.get("/needs/{project_id}", response_model=List[SupplyNeedItem], summary="Потребность в материалах по проекту")
async def get_supply_needs(project_id: int):
    return [SupplyNeedItem(material_id=1, material_name="Цемент М400", required_quantity=200.0, available_quantity=100.0, deficit=100.0)]


@router.get("/warehouse", summary="Состояние склада")
async def get_warehouse():
    return {
        "capacity_max": 1000.0,
        "capacity_used": 350.0,
        "items": [{"material_id": 1, "material_name": "Цемент М400", "quantity": 100.0, "unit": "т"}],
    }
