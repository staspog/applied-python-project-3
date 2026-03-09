from __future__ import annotations

import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from app.db.models import Link, LinkArchive
from app.services.cache import link_cache_key, stats_cache_key


async def run_expiry_cleanup_loop(
    *,
    engine: AsyncEngine,
    redis_client,
    interval_seconds: int,
    batch_size: int,
) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    while True:
        try:
            await _cleanup_once(
                session_factory=session_factory,
                redis_client=redis_client,
                batch_size=batch_size,
            )
        except Exception:
            # не даём единичным ошибкам БД/Redis убить весь фон очистки
            # просто пропускаем эту итерацию и продолжаем работать дальше
            pass
        await asyncio.sleep(interval_seconds)


async def _cleanup_once(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client,
    batch_size: int,
) -> None:
    now = func.now()
    async with session_factory() as session:
        res = await session.execute(
            select(Link).where(Link.expires_at.is_not(None), Link.expires_at <= now).limit(batch_size)
        )
        expired_links = list(res.scalars().all())
        if not expired_links:
            return

        archives = [
            LinkArchive(
                short_code=l.short_code,
                original_url=l.original_url,
                created_at=l.created_at,
                expires_at=l.expires_at,
                clicks_count=l.clicks_count,
                last_accessed_at=l.last_accessed_at,
                owner_user_id=l.owner_user_id,
                owner_guest_id=l.owner_guest_id,
                archived_reason="expired",
            )
            for l in expired_links
        ]
        session.add_all(archives)
        ids = [l.id for l in expired_links]
        await session.execute(delete(Link).where(Link.id.in_(ids)))
        await session.commit()

    keys: list[str] = []
    for l in expired_links:
        keys.append(link_cache_key(l.short_code))
        keys.append(stats_cache_key(l.short_code))
    if keys:
        try:
            await redis_client.delete(*keys)
        except Exception:
            pass
