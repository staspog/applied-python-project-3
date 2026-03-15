"""Юнит-тесты сервиса links (БД): create_link, get_active, update/delete as user/guest."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link, User
from app.services.links import (
    create_link,
    delete_link_as_guest,
    delete_link_as_user,
    get_active_link_by_short_code,
    get_link_by_short_code,
    list_archived_links,
    search_links_by_original_url,
    update_link_as_guest,
    update_link_as_user,
)


@pytest.fixture
async def user_in_db(session_factory):
    """Уникальный пользователь на каждый тест (общая in-memory БД в сессии)."""
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        u = User(
            username=f"svc_{suffix}",
            email=f"svc_{suffix}@x.com",
            password_hash="hash",
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u.id


@pytest.fixture
async def link_in_db(session_factory, user_in_db):
    """Уникальная ссылка на каждый тест (общая БД в сессии)."""
    code = f"sc{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        link = Link(
            short_code=code,
            original_url="https://example.com/one",
            owner_user_id=user_in_db,
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link.short_code, user_in_db


@pytest.mark.asyncio
async def test_get_link_by_short_code_missing(session_factory):
    async with session_factory() as session:
        assert await get_link_by_short_code(session, "nonexistent") is None


@pytest.mark.asyncio
async def test_get_active_link_expired_archives(session_factory, user_in_db):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with session_factory() as session:
        link = Link(
            short_code="exp1",
            original_url="https://example.com/exp",
            owner_user_id=user_in_db,
            expires_at=past,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        result = await get_active_link_by_short_code(session, "exp1")
        assert result is None
    async with session_factory() as session:
        archived = await list_archived_links(
            session, owner_user_id=user_in_db, owner_guest_id=None, limit=5, offset=0
        )
        assert len(archived) == 1
        assert archived[0].short_code == "exp1"
        assert archived[0].archived_reason == "expired"


@pytest.mark.asyncio
async def test_create_link_custom_alias_exists_raises(session_factory, user_in_db):
    async with session_factory() as session:
        link = Link(
            short_code="dup",
            original_url="https://example.com/first",
            owner_user_id=user_in_db,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Alias already exists"):
            await create_link(
                session,
                original_url="https://example.com/second",
                custom_alias="dup",
                expires_at=None,
                owner_user_id=user_in_db,
                owner_guest_id=None,
            )


@pytest.mark.asyncio
async def test_update_link_as_user_not_found(session_factory, user_in_db):
    async with session_factory() as session:
        with pytest.raises(LookupError, match="Not found"):
            await update_link_as_user(
                session,
                short_code="nonexistent",
                owner_user_id=user_in_db,
                new_original_url="https://example.com/x",
                new_custom_alias=None,
                new_expires_at=None,
            )


@pytest.mark.asyncio
async def test_update_link_as_user_forbidden(session_factory, link_in_db, user_in_db):
    short_code, owner_id = link_in_db
    other_id = owner_id + 999
    async with session_factory() as session:
        with pytest.raises(PermissionError, match="Forbidden"):
            await update_link_as_user(
                session,
                short_code=short_code,
                owner_user_id=other_id,
                new_original_url="https://example.com/hack",
                new_custom_alias=None,
                new_expires_at=None,
            )


@pytest.mark.asyncio
async def test_update_link_as_user_success(session_factory, link_in_db, user_in_db):
    short_code, owner_id = link_in_db
    async with session_factory() as session:
        link = await update_link_as_user(
            session,
            short_code=short_code,
            owner_user_id=owner_id,
            new_original_url="https://example.com/updated",
            new_custom_alias=None,
            new_expires_at=None,
        )
        assert link.original_url == "https://example.com/updated"


@pytest.mark.asyncio
async def test_delete_link_as_user_not_found(session_factory, user_in_db):
    async with session_factory() as session:
        with pytest.raises(LookupError, match="Not found"):
            await delete_link_as_user(
                session, short_code="nonexistent", owner_user_id=user_in_db
            )


@pytest.mark.asyncio
async def test_delete_link_as_user_forbidden(session_factory, link_in_db, user_in_db):
    short_code, owner_id = link_in_db
    other_id = owner_id + 999
    async with session_factory() as session:
        with pytest.raises(PermissionError, match="Forbidden"):
            await delete_link_as_user(
                session, short_code=short_code, owner_user_id=other_id
            )


@pytest.mark.asyncio
async def test_update_link_as_guest_forbidden_wrong_guest(session_factory, user_in_db):
    async with session_factory() as session:
        link = Link(
            short_code="g1",
            original_url="https://example.com/g",
            owner_guest_id="guest-a",
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(PermissionError, match="Forbidden"):
            await update_link_as_guest(
                session,
                short_code="g1",
                owner_guest_id="guest-b",
                new_original_url="https://example.com/x",
                new_custom_alias=None,
                new_expires_at=None,
            )


@pytest.mark.asyncio
async def test_delete_link_as_guest_forbidden_wrong_guest(session_factory):
    async with session_factory() as session:
        link = Link(
            short_code="g2",
            original_url="https://example.com/g",
            owner_guest_id="guest-x",
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(PermissionError, match="Forbidden"):
            await delete_link_as_guest(
                session, short_code="g2", owner_guest_id="guest-y"
            )


@pytest.mark.asyncio
async def test_search_links_by_original_url(session_factory, user_in_db):
    async with session_factory() as session:
        link = Link(
            short_code="s1",
            original_url="https://example.com/search-me",
            owner_user_id=user_in_db,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        found = await search_links_by_original_url(
            session, "https://example.com/search-me"
        )
        assert len(found) == 1
        assert found[0].short_code == "s1"
    async with session_factory() as session:
        empty = await search_links_by_original_url(
            session, "https://example.com/not-created"
        )
        assert empty == []


@pytest.mark.asyncio
async def test_list_archived_links_no_owner_returns_empty(session_factory):
    """Когда ни user, ни guest не заданы — возвращается [] (ветка else)."""
    async with session_factory() as session:
        out = await list_archived_links(
            session, owner_user_id=None, owner_guest_id=None, limit=10, offset=0
        )
        assert out == []
