from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.db.session import get_db

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Получить токен доступа")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    access_token = create_access_token({"sub": str(user.user_id)})
    refresh_token = create_refresh_token({"sub": str(user.user_id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse, summary="Обновить токен доступа")
async def refresh_token(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный refresh токен",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный тип токена",
        )

    user_id = payload.get("sub")
    access_token = create_access_token({"sub": user_id})
    new_refresh_token = create_refresh_token({"sub": user_id})
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", summary="Выйти из системы")
async def logout():
    return {"detail": "Выход выполнен успешно"}
