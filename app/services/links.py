from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link, LinkArchive
from app.services.short_code import generate_short_code


def _is_expired(expires_at: datetime | None) -> bool:
    if not expires_at:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


async def archive_and_delete(
    session: AsyncSession,
    link: Link,
    *,
    reason: str,
) -> None:
    archive = LinkArchive(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
        clicks_count=link.clicks_count,
        last_accessed_at=link.last_accessed_at,
        owner_user_id=link.owner_user_id,
        owner_guest_id=link.owner_guest_id,
        archived_reason=reason,
    )
    session.add(archive)
    await session.execute(delete(Link).where(Link.id == link.id))
    await session.commit()


async def create_link(
    session: AsyncSession,
    *,
    original_url: str,
    custom_alias: str | None,
    expires_at: datetime | None,
    owner_user_id: int | None,
    owner_guest_id: str | None,
) -> Link:
    if custom_alias:
        short_code = custom_alias
        link = Link(
            short_code=short_code,
            original_url=original_url,
            expires_at=expires_at,
            owner_user_id=owner_user_id,
            owner_guest_id=owner_guest_id,
        )
        session.add(link)
        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise ValueError("Alias already exists") from e
        await session.refresh(link)
        return link

    for _ in range(10):
        short_code = generate_short_code()
        link = Link(
            short_code=short_code,
            original_url=original_url,
            expires_at=expires_at,
            owner_user_id=owner_user_id,
            owner_guest_id=owner_guest_id,
        )
        session.add(link)
        try:
            await session.commit()
            await session.refresh(link)
            return link
        except IntegrityError:
            await session.rollback()
            continue
    raise RuntimeError("Failed to generate unique short code")


async def get_link_by_short_code(session: AsyncSession, short_code: str) -> Link | None:
    res = await session.execute(select(Link).where(Link.short_code == short_code))
    return res.scalar_one_or_none()

async def get_active_link_by_short_code(
    session: AsyncSession, short_code: str
) -> Link | None:
    link = await get_link_by_short_code(session, short_code)
    if not link:
        return None
    if _is_expired(link.expires_at):
        await archive_and_delete(session, link, reason="expired")
        return None
    return link


async def touch_link(session: AsyncSession, short_code: str) -> bool:
    now = func.now()
    stmt = (
        update(Link)
        .where(
            and_(
                Link.short_code == short_code,
                or_(Link.expires_at.is_(None), Link.expires_at > now),
            )
        )
        .values(clicks_count=Link.clicks_count + 1, last_accessed_at=now)
    )
    res = await session.execute(stmt)
    if res.rowcount and res.rowcount > 0:
        await session.commit()
        return True
    return False


async def update_link_as_user(
    session: AsyncSession,
    *,
    short_code: str,
    owner_user_id: int,
    new_original_url: str | None,
    new_custom_alias: str | None,
    new_expires_at: datetime | None,
) -> Link:
    link = await get_link_by_short_code(session, short_code)
    if not link:
        raise LookupError("Not found")
    if _is_expired(link.expires_at):
        await archive_and_delete(session, link, reason="expired")
        raise LookupError("Not found")
    if link.owner_user_id != owner_user_id:
        raise PermissionError("Forbidden")

    if new_original_url is not None:
        link.original_url = new_original_url
    if new_expires_at is not None:
        link.expires_at = new_expires_at
    if new_custom_alias is not None and new_custom_alias != link.short_code:
        link.short_code = new_custom_alias

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Alias already exists") from e
    await session.refresh(link)
    return link


async def update_link_as_guest(
    session: AsyncSession,
    *,
    short_code: str,
    owner_guest_id: str,
    new_original_url: str | None,
    new_custom_alias: str | None,
    new_expires_at: datetime | None,
) -> Link:
    link = await get_link_by_short_code(session, short_code)
    if not link:
        raise LookupError("Not found")
    if _is_expired(link.expires_at):
        await archive_and_delete(session, link, reason="expired")
        raise LookupError("Not found")
    if link.owner_guest_id != owner_guest_id:
        raise PermissionError("Forbidden")
    if link.owner_user_id is not None:
        raise PermissionError("Forbidden")

    if new_original_url is not None:
        link.original_url = new_original_url
    if new_expires_at is not None:
        link.expires_at = new_expires_at
    if new_custom_alias is not None and new_custom_alias != link.short_code:
        link.short_code = new_custom_alias

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Alias already exists") from e
    await session.refresh(link)
    return link


async def delete_link_as_user(
    session: AsyncSession,
    *,
    short_code: str,
    owner_user_id: int,
) -> None:
    link = await get_link_by_short_code(session, short_code)
    if not link:
        raise LookupError("Not found")
    if _is_expired(link.expires_at):
        await archive_and_delete(session, link, reason="expired")
        raise LookupError("Not found")
    if link.owner_user_id != owner_user_id:
        raise PermissionError("Forbidden")
    await archive_and_delete(session, link, reason="deleted")


async def delete_link_as_guest(
    session: AsyncSession,
    *,
    short_code: str,
    owner_guest_id: str,
) -> None:
    link = await get_link_by_short_code(session, short_code)
    if not link:
        raise LookupError("Not found")
    if _is_expired(link.expires_at):
        await archive_and_delete(session, link, reason="expired")
        raise LookupError("Not found")
    if link.owner_guest_id != owner_guest_id:
        raise PermissionError("Forbidden")
    if link.owner_user_id is not None:
        raise PermissionError("Forbidden")
    await archive_and_delete(session, link, reason="deleted")


async def search_links_by_original_url(
    session: AsyncSession, original_url: str
) -> list[Link]:
    now = func.now()
    res = await session.execute(
        select(Link).where(
            and_(
                Link.original_url == original_url,
                or_(Link.expires_at.is_(None), Link.expires_at > now),
            )
        )
    )
    return list(res.scalars().all())


async def list_archived_links(
    session: AsyncSession,
    *,
    owner_user_id: int | None,
    owner_guest_id: str | None,
    limit: int,
    offset: int,
) -> list[LinkArchive]:
    stmt = select(LinkArchive).order_by(LinkArchive.archived_at.desc()).limit(limit).offset(offset)
    if owner_user_id is not None:
        stmt = stmt.where(LinkArchive.owner_user_id == owner_user_id)
    elif owner_guest_id is not None:
        stmt = stmt.where(LinkArchive.owner_guest_id == owner_guest_id)
    else:
        return []
    res = await session.execute(stmt)
    return list(res.scalars().all())

