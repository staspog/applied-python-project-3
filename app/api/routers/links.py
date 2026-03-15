from __future__ import annotations

from typing import Annotated

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Link
from app.db.session import get_db_session
from app.deps.auth import get_current_user, get_optional_user
from app.deps.redis import get_redis
from app.schemas.archive import ArchivedLinkOut
from app.schemas.links import LinkCreate, LinkOut, LinkStats, LinkUpdate
from app.services.cache import (
    cache_link,
    cache_stats,
    get_cached_link,
    get_cached_stats,
    invalidate_link,
)
from app.services.guests import get_guest_id, get_or_create_guest_id
from app.services.links import (
    create_link,
    delete_link_as_guest,
    delete_link_as_user,
    get_active_link_by_short_code,
    list_archived_links,
    search_links_by_original_url,
    touch_link,
    update_link_as_guest,
    update_link_as_user,
)

router = APIRouter()


@router.post("/links/shorten", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def shorten_link(
    request: Request,
    data: LinkCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user=Depends(get_optional_user),
    redis_client=Depends(get_redis),
):
    owner_user_id = user.id if user else None
    owner_guest_id = None if user else get_or_create_guest_id(request)

    if owner_user_id is None:
        rl_key = f"rl:guest:{owner_guest_id}:create"
        count = await redis_client.incr(rl_key)
        if count == 1:
            await redis_client.expire(rl_key, 60)
        if count > settings.guest_create_limit_per_minute:
            raise HTTPException(status_code=429, detail="Guest rate limit exceeded")

        active_count_res = await session.execute(
            select(func.count())
            .select_from(Link)
            .where(
                Link.owner_guest_id == owner_guest_id,
                or_(Link.expires_at.is_(None), Link.expires_at > func.now()),
            )
        )
        active_count = int(active_count_res.scalar_one())
        if active_count >= settings.guest_max_active_links:
            raise HTTPException(status_code=429, detail="Guest active links limit exceeded")

    try:
        link = await create_link(
            session,
            original_url=str(data.original_url),
            custom_alias=data.custom_alias,
            expires_at=data.expires_at,
            owner_user_id=owner_user_id,
            owner_guest_id=owner_guest_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return LinkOut(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.get("/links/search", response_model=list[LinkOut])
async def search_links(
    original_url: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    links = await search_links_by_original_url(session, original_url)
    return [
        LinkOut(
            short_code=l.short_code,
            original_url=l.original_url,
            created_at=l.created_at,
            expires_at=l.expires_at,
        )
        for l in links
    ]


@router.get("/links/expired", response_model=list[ArchivedLinkOut])
async def list_expired_links(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user=Depends(get_optional_user),
    limit: int = 50,
    offset: int = 0,
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    owner_user_id = user.id if user else None
    owner_guest_id = None if user else get_guest_id(request)
    if owner_user_id is None and owner_guest_id is None:
        raise HTTPException(status_code=401, detail="Authentication or guest session required")

    archived = await list_archived_links(
        session,
        owner_user_id=owner_user_id,
        owner_guest_id=owner_guest_id,
        limit=limit,
        offset=offset,
    )
    return [
        ArchivedLinkOut(
            short_code=a.short_code,
            original_url=a.original_url,
            created_at=a.created_at,
            expires_at=a.expires_at,
            clicks_count=a.clicks_count,
            last_accessed_at=a.last_accessed_at,
            archived_at=a.archived_at,
            archived_reason=a.archived_reason,
        )
        for a in archived
    ]


@router.get("/links/{short_code}", response_class=RedirectResponse)
async def redirect_short_code(
    short_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client=Depends(get_redis),
):
    cached = await get_cached_link(redis_client, short_code)
    if cached:
        expires_at_raw = cached.get("expires_at")
        if expires_at_raw:
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                expires_at = None
            if expires_at:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    await invalidate_link(redis_client, short_code)
                    cached = None

    if cached:
        ok = await touch_link(session, short_code)
        if ok:
            return cached["original_url"]
        await invalidate_link(redis_client, short_code)

    link = await get_active_link_by_short_code(session, short_code)
    if not link:
        await invalidate_link(redis_client, short_code)
        raise HTTPException(status_code=404, detail="Link not found")

    await touch_link(session, short_code)
    await cache_link(
        redis_client,
        short_code=link.short_code,
        original_url=link.original_url,
        expires_at=link.expires_at,
    )
    return link.original_url


@router.get("/links/{short_code}/stats", response_model=LinkStats)
async def link_stats(
    short_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client=Depends(get_redis),
):
    cached = await get_cached_stats(redis_client, short_code)
    if cached:
        return cached
    link = await get_active_link_by_short_code(session, short_code)
    if not link:
        await invalidate_link(redis_client, short_code)
        raise HTTPException(status_code=404, detail="Link not found")
    stats = LinkStats(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        clicks_count=link.clicks_count,
        last_accessed_at=link.last_accessed_at,
        expires_at=link.expires_at,
    )
    await cache_stats(redis_client, short_code=short_code, stats=stats.model_dump(mode="json"))
    return stats


@router.put("/links/{short_code}", response_model=LinkOut)
async def update_link(
    short_code: str,
    data: LinkUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user=Depends(get_current_user),
    redis_client=Depends(get_redis),
):
    try:
        link = await update_link_as_user(
            session,
            short_code=short_code,
            owner_user_id=user.id,
            new_original_url=str(data.original_url) if data.original_url else None,
            new_custom_alias=data.custom_alias,
            new_expires_at=data.expires_at,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Link not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await invalidate_link(redis_client, short_code)
    if link.short_code != short_code:
        await invalidate_link(redis_client, link.short_code)
    return LinkOut(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.delete("/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user=Depends(get_current_user),
    redis_client=Depends(get_redis),
):
    try:
        await delete_link_as_user(session, short_code=short_code, owner_user_id=user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Link not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    await invalidate_link(redis_client, short_code)
    return None


@router.put("/guest/links/{short_code}", response_model=LinkOut)
async def update_guest_link(
    request: Request,
    short_code: str,
    data: LinkUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client=Depends(get_redis),
):
    guest_id = get_guest_id(request)
    if not guest_id:
        raise HTTPException(status_code=401, detail="Guest session required")
    try:
        link = await update_link_as_guest(
            session,
            short_code=short_code,
            owner_guest_id=guest_id,
            new_original_url=str(data.original_url) if data.original_url else None,
            new_custom_alias=data.custom_alias,
            new_expires_at=data.expires_at,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Link not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await invalidate_link(redis_client, short_code)
    if link.short_code != short_code:
        await invalidate_link(redis_client, link.short_code)
    return LinkOut(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.delete("/guest/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guest_link(
    request: Request,
    short_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis_client=Depends(get_redis),
):
    guest_id = get_guest_id(request)
    if not guest_id:
        raise HTTPException(status_code=401, detail="Guest session required")
    try:
        await delete_link_as_guest(session, short_code=short_code, owner_guest_id=guest_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Link not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    await invalidate_link(redis_client, short_code)
    return None
