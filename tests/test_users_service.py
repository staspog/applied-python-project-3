"""Юнит-тесты сервиса users."""
from __future__ import annotations

import uuid

import pytest

from app.schemas.auth import UserCreate
from app.services.users import (
    authenticate_user,
    create_user,
    get_user_by_id,
    get_user_by_username,
)


@pytest.mark.asyncio
async def test_get_user_by_username_missing(session_factory):
    async with session_factory() as session:
        assert await get_user_by_username(session, "nonexistent") is None


@pytest.mark.asyncio
async def test_get_user_by_id_missing(session_factory):
    async with session_factory() as session:
        assert await get_user_by_id(session, 99999) is None


@pytest.mark.asyncio
async def test_create_user_duplicate_email_raises(session_factory):
    email = f"dup_{uuid.uuid4().hex[:8]}@x.com"
    data = UserCreate(username=f"u1_{uuid.uuid4().hex[:6]}", password="pass12", email=email)
    async with session_factory() as session:
        await create_user(session, data)
    async with session_factory() as session:
        data2 = UserCreate(username=f"u2_{uuid.uuid4().hex[:6]}", password="pass12", email=email)
        with pytest.raises(ValueError, match="User already exists"):
            await create_user(session, data2)


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(session_factory):
    uname = f"auth_u_{uuid.uuid4().hex[:6]}"
    data = UserCreate(username=uname, password="correct", email=f"{uname}@x.com")
    async with session_factory() as session:
        await create_user(session, data)
    async with session_factory() as session:
        user = await authenticate_user(session, uname, "wrong")
        assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(session_factory):
    async with session_factory() as session:
        user = await authenticate_user(session, "no_such_user", "any")
        assert user is None
