from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


_STUB_USER = UserOut(id=1, username="admin", email="admin@example.com", role="admin", is_active=True)


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
async def get_me():
    return _STUB_USER


@router.get("/", response_model=List[UserOut], summary="Список пользователей")
async def list_users():
    return [_STUB_USER]


@router.post("/", response_model=UserOut, status_code=201, summary="Создать пользователя")
async def create_user(body: UserCreate):
    return UserOut(id=2, username=body.username, email=body.email, role=body.role, is_active=True)


@router.get("/{user_id}", response_model=UserOut, summary="Получить пользователя")
async def get_user(user_id: int):
    return UserOut(id=user_id, username="stub", email="stub@example.com", role="viewer", is_active=True)


@router.patch("/{user_id}", response_model=UserOut, summary="Обновить пользователя")
async def update_user(user_id: int, body: UserUpdate):
    return UserOut(id=user_id, username="stub", email=body.email or "stub@example.com", role=body.role or "viewer", is_active=True)


@router.delete("/{user_id}", status_code=204, summary="Удалить пользователя")
async def delete_user(user_id: int):
    return None
