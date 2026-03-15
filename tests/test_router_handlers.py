"""Прямой вызов обработчиков роутера для покрытия redirect/stats/update/delete."""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from app.api.routers.links import (
    delete_guest_link,
    delete_link,
    link_stats,
    redirect_short_code,
    update_guest_link,
    update_link,
)
from app.db.models import Link, User
from app.schemas.links import LinkUpdate


async def test_redirect_handler_direct_call(session_factory, redis_client):
    """Прямой вызов redirect_short_code: кэш пуст, загрузка из БД, cache_link."""
    code = f"r{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        user = User(username=f"r1_{uuid.uuid4().hex[:6]}", email=f"r1_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        link = Link(
            short_code=code,
            original_url="https://example.com/direct",
            owner_user_id=user.id,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        result = await redirect_short_code(
            short_code=code,
            session=session,
            redis_client=redis_client,
        )
    assert result == "https://example.com/direct"


async def test_link_stats_handler_direct_call(session_factory, redis_client):
    """Прямой вызов link_stats: кэш пуст, загрузка из БД, cache_stats."""
    code = f"s{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        user = User(username=f"s1_{uuid.uuid4().hex[:6]}", email=f"s1_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        link = Link(
            short_code=code,
            original_url="https://example.com/stats",
            owner_user_id=user.id,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        stats = await link_stats(
            short_code=code,
            session=session,
            redis_client=redis_client,
        )
    assert stats.short_code == code
    assert str(stats.original_url) == "https://example.com/stats"


async def test_update_link_handler_direct_call(session_factory, redis_client):
    """Прямой вызов update_link: успех и инвалидация обоих ключей при смене alias."""
    code = f"upd{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        user = User(username=f"u1_{uuid.uuid4().hex[:6]}", email=f"u1_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        link = Link(
            short_code=code,
            original_url="https://example.com/old",
            owner_user_id=user.id,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        data = LinkUpdate(original_url="https://example.com/new")
        out = await update_link(
            short_code=code,
            data=data,
            session=session,
            user=user,
            redis_client=redis_client,
        )
    assert out.short_code == code
    assert str(out.original_url) == "https://example.com/new"


async def test_update_link_handler_change_alias(session_factory, redis_client):
    """update_link со сменой short_code — инвалидация старого и нового."""
    old_code = f"old{uuid.uuid4().hex[:6]}"
    new_code = f"new{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        user = User(username=f"u2_{uuid.uuid4().hex[:6]}", email=f"u2_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        link = Link(
            short_code=old_code,
            original_url="https://example.com/x",
            owner_user_id=user.id,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        data = LinkUpdate(custom_alias=new_code)
        out = await update_link(
            short_code=old_code,
            data=data,
            session=session,
            user=user,
            redis_client=redis_client,
        )
    assert out.short_code == new_code


async def test_delete_link_handler_direct_call(session_factory, redis_client):
    """Прямой вызов delete_link."""
    code = f"del{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        user = User(username=f"d1_{uuid.uuid4().hex[:6]}", email=f"d1_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        link = Link(
            short_code=code,
            original_url="https://example.com/del",
            owner_user_id=user.id,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        result = await delete_link(
            short_code=code,
            session=session,
            user=user,
            redis_client=redis_client,
        )
    assert result is None


async def test_update_link_404(session_factory, redis_client):
    """update_link: ссылка не найдена — 404."""
    async with session_factory() as session:
        user = User(username=f"u404_{uuid.uuid4().hex[:6]}", email=f"u404_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    async with session_factory() as session:
        try:
            await update_link(
                short_code="nonexistent",
                data=LinkUpdate(original_url="https://x.com"),
                session=session,
                user=user,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 404


async def test_update_link_403(session_factory, redis_client):
    """update_link: не владелец — 403."""
    suf = uuid.uuid4().hex[:6]
    async with session_factory() as session:
        owner = User(username=f"own_{suf}", email=f"own_{suf}@x.com", password_hash="h")
        other = User(username=f"oth_{suf}", email=f"oth_{suf}@x.com", password_hash="h")
        session.add_all([owner, other])
        await session.commit()
        await session.refresh(owner)
        await session.refresh(other)
        sc = f"f1_{suf}"
        link = Link(
            short_code=sc,
            original_url="https://example.com/f",
            owner_user_id=owner.id,
        )
        session.add(link)
        await session.commit()
    async with session_factory() as session:
        try:
            await update_link(
                short_code=sc,
                data=LinkUpdate(original_url="https://x.com"),
                session=session,
                user=other,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 403


async def test_delete_link_404(session_factory, redis_client):
    """delete_link: ссылка не найдена — 404."""
    async with session_factory() as session:
        user = User(username=f"d404_{uuid.uuid4().hex[:6]}", email=f"d404_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    async with session_factory() as session:
        try:
            await delete_link(
                short_code="nonexistent",
                session=session,
                user=user,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 404


async def test_delete_guest_link_direct(app, session_factory, redis_client):
    """Прямой вызов delete_guest_link с request с guest_id."""
    from unittest.mock import MagicMock
    code = f"gdel{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        link = Link(
            short_code=code,
            original_url="https://example.com/g",
            owner_guest_id="guest-123",
        )
        session.add(link)
        await session.commit()
    request = MagicMock()
    request.session = {"guest_id": "guest-123"}
    async with session_factory() as session:
        result = await delete_guest_link(
            request=request,
            short_code=code,
            session=session,
            redis_client=redis_client,
        )
    assert result is None


async def test_redirect_handler_404(session_factory, redis_client):
    """redirect_short_code: ссылка не найдена — HTTPException 404."""
    async with session_factory() as session:
        try:
            await redirect_short_code(
                short_code="nonexistent_code_xyz",
                session=session,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 404


async def test_link_stats_handler_404(session_factory, redis_client):
    """link_stats: ссылка не найдена — HTTPException 404."""
    async with session_factory() as session:
        try:
            await link_stats(
                short_code="nonexistent_code_xyz",
                session=session,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 404


async def test_update_link_409_alias_exists(session_factory, redis_client):
    """update_link: новый alias уже занят — 409."""
    a1 = f"a1_{uuid.uuid4().hex[:6]}"
    a2 = f"a2_{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        user = User(username=f"u409_{uuid.uuid4().hex[:6]}", email=f"u409_{uuid.uuid4().hex[:6]}@x.com", password_hash="h")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(Link(short_code=a1, original_url="https://x.com/1", owner_user_id=user.id))
        session.add(Link(short_code=a2, original_url="https://x.com/2", owner_user_id=user.id))
        await session.commit()
    async with session_factory() as session:
        try:
            await update_link(
                short_code=a1,
                data=LinkUpdate(custom_alias=a2),
                session=session,
                user=user,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 409


async def test_delete_link_403(session_factory, redis_client):
    """delete_link: не владелец — 403."""
    suf = uuid.uuid4().hex[:6]
    async with session_factory() as session:
        owner = User(username=f"do_{suf}", email=f"do_{suf}@x.com", password_hash="h")
        other = User(username=f"de_{suf}", email=f"de_{suf}@x.com", password_hash="h")
        session.add_all([owner, other])
        await session.commit()
        await session.refresh(owner)
        await session.refresh(other)
        sc = f"del403_{suf}"
        session.add(Link(short_code=sc, original_url="https://x.com", owner_user_id=owner.id))
        await session.commit()
    async with session_factory() as session:
        try:
            await delete_link(short_code=sc, session=session, user=other, redis_client=redis_client)
        except HTTPException as e:
            assert e.status_code == 403


async def test_update_guest_link_401_no_session(session_factory, redis_client):
    """update_guest_link: нет guest_id в session — 401."""
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {}
    async with session_factory() as session:
        try:
            await update_guest_link(
                request=request, short_code="any", data=LinkUpdate(), session=session, redis_client=redis_client
            )
        except HTTPException as e:
            assert e.status_code == 401


async def test_delete_guest_link_401_no_session(session_factory, redis_client):
    """delete_guest_link: нет guest_id — 401."""
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {}
    async with session_factory() as session:
        try:
            await delete_guest_link(request=request, short_code="any", session=session, redis_client=redis_client)
        except HTTPException as e:
            assert e.status_code == 401


async def test_update_guest_link_404(session_factory, redis_client):
    """update_guest_link: ссылка не найдена — 404."""
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {"guest_id": "g404"}
    async with session_factory() as session:
        try:
            await update_guest_link(
                request=request,
                short_code="nonexistent_guest_link",
                data=LinkUpdate(original_url="https://x.com"),
                session=session,
                redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 404


async def test_update_guest_link_403_wrong_guest(session_factory, redis_client):
    """update_guest_link: не владелец-гость — 403."""
    from unittest.mock import MagicMock
    code = f"g403_{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        session.add(
            Link(short_code=code, original_url="https://x.com", owner_guest_id="owner-guest")
        )
        await session.commit()
    request = MagicMock()
    request.session = {"guest_id": "other-guest"}
    async with session_factory() as session:
        try:
            await update_guest_link(
                request=request, short_code=code, data=LinkUpdate(original_url="https://y.com"),
                session=session, redis_client=redis_client,
            )
        except HTTPException as e:
            assert e.status_code == 403


async def test_update_guest_link_change_alias(session_factory, redis_client):
    """update_guest_link со сменой short_code — инвалидация обоих ключей."""
    from unittest.mock import MagicMock
    old_c = f"oldg{uuid.uuid4().hex[:6]}"
    new_c = f"newg{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        session.add(
            Link(short_code=old_c, original_url="https://x.com", owner_guest_id="gch")
        )
        await session.commit()
    request = MagicMock()
    request.session = {"guest_id": "gch"}
    async with session_factory() as session:
        out = await update_guest_link(
            request=request, short_code=old_c, data=LinkUpdate(custom_alias=new_c),
            session=session, redis_client=redis_client,
        )
    assert out.short_code == new_c


async def test_delete_guest_link_404(session_factory, redis_client):
    """delete_guest_link: ссылка не найдена — 404."""
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {"guest_id": "gdel404"}
    async with session_factory() as session:
        try:
            await delete_guest_link(
                request=request, short_code="nonexistent_guest", session=session, redis_client=redis_client
            )
        except HTTPException as e:
            assert e.status_code == 404


async def test_delete_guest_link_403(session_factory, redis_client):
    """delete_guest_link: не владелец-гость — 403."""
    from unittest.mock import MagicMock
    code = f"gdel403_{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        session.add(Link(short_code=code, original_url="https://x.com", owner_guest_id="owner"))
        await session.commit()
    request = MagicMock()
    request.session = {"guest_id": "other"}
    async with session_factory() as session:
        try:
            await delete_guest_link(request=request, short_code=code, session=session, redis_client=redis_client)
        except HTTPException as e:
            assert e.status_code == 403


async def test_update_guest_link_direct(app, session_factory, redis_client):
    """Прямой вызов update_guest_link."""
    from unittest.mock import MagicMock
    code = f"gup{uuid.uuid4().hex[:6]}"
    async with session_factory() as session:
        link = Link(
            short_code=code,
            original_url="https://example.com/g",
            owner_guest_id="guest-456",
        )
        session.add(link)
        await session.commit()
    request = MagicMock()
    request.session = {"guest_id": "guest-456"}
    data = LinkUpdate(original_url="https://example.com/updated")
    async with session_factory() as session:
        out = await update_guest_link(
            request=request,
            short_code=code,
            data=data,
            session=session,
            redis_client=redis_client,
        )
    assert out.short_code == code
    assert str(out.original_url) == "https://example.com/updated"
