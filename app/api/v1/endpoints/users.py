from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.user import UserOut, UserCreate, UserUpdate
from app.models.user import User
from app.core.security import get_password_hash
from app.db.session import get_db
from app.api.deps import get_current_user, require_admin

router = APIRouter()


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=List[UserOut], summary="Список пользователей")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.post("/", response_model=UserOut, status_code=201, summary="Создать пользователя")
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует",
        )

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@router.get("/{user_id}", response_model=UserOut, summary="Получить пользователя")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="Обновить пользователя")
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if body.email is not None:
        user.email = body.email
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    return user


@router.delete("/{user_id}", status_code=204, summary="Удалить пользователя")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.delete(user)
