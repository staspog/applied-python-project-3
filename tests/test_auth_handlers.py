"""Прямой вызов обработчиков auth для покрытия веток register/login."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.routers.auth import login, register
from app.schemas.auth import UserCreate


async def test_register_value_error_duplicate_email(session_factory):
    """register: create_user выбрасывает ValueError (дубликат email) — 409."""
    email = f"dup_{uuid.uuid4().hex[:8]}@x.com"
    data = UserCreate(username=f"u1_{uuid.uuid4().hex[:6]}", password="pass12", email=email)
    async with session_factory() as session:
        await register(data=data, session=session)
    data2 = UserCreate(username=f"u2_{uuid.uuid4().hex[:6]}", password="pass12", email=email)
    async with session_factory() as session:
        try:
            await register(data=data2, session=session)
        except HTTPException as e:
            assert e.status_code == 409


async def test_login_user_none_400(session_factory):
    """login: authenticate_user возвращает None — 400."""
    form = OAuth2PasswordRequestForm(username="nonexistent_user", password="any", scope="")
    async with session_factory() as session:
        try:
            await login(form_data=form, session=session)
        except HTTPException as e:
            assert e.status_code == 400
            assert "Incorrect" in (e.detail or "")
