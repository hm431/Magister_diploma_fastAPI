from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class MaterialOut(BaseModel):
    id: int
    name: str
    unit: str
    category: str
    price_per_unit: float
    stock_quantity: float


class MaterialCreate(BaseModel):
    name: str
    unit: str
    category: str
    price_per_unit: float


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    price_per_unit: Optional[float] = None
    stock_quantity: Optional[float] = None


_STUB = MaterialOut(id=1, name="Цемент М400", unit="т", category="Вяжущие", price_per_unit=7500.0, stock_quantity=100.0)


@router.get("/", response_model=List[MaterialOut], summary="Справочник материалов")
async def list_materials(category: Optional[str] = None):
    return [_STUB]


@router.post("/", response_model=MaterialOut, status_code=201, summary="Добавить материал в справочник")
async def create_material(body: MaterialCreate):
    return MaterialOut(id=2, name=body.name, unit=body.unit, category=body.category, price_per_unit=body.price_per_unit, stock_quantity=0.0)


@router.get("/{material_id}", response_model=MaterialOut, summary="Получить материал")
async def get_material(material_id: int):
    return MaterialOut(id=material_id, name="Заглушка", unit="шт", category="Прочее", price_per_unit=0.0, stock_quantity=0.0)


@router.patch("/{material_id}", response_model=MaterialOut, summary="Обновить материал")
async def update_material(material_id: int, body: MaterialUpdate):
    return MaterialOut(id=material_id, name=body.name or "Заглушка", unit=body.unit or "шт", category="Прочее", price_per_unit=body.price_per_unit or 0.0, stock_quantity=body.stock_quantity or 0.0)


@router.delete("/{material_id}", status_code=204, summary="Удалить материал из справочника")
async def delete_material(material_id: int):
    return None
