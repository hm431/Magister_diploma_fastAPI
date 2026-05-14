from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse, summary="Получить токен доступа")
async def login(body: LoginRequest):
    return {"access_token": "stub_access_token", "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse, summary="Обновить токен доступа")
async def refresh_token(body: RefreshRequest):
    return {"access_token": "stub_refreshed_token", "token_type": "bearer"}


@router.post("/logout", summary="Выйти из системы")
async def logout():
    return {"detail": "Выход выполнен успешно"}
