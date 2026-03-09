from __future__ import annotations

import json
from datetime import datetime, timezone


def link_cache_key(short_code: str) -> str:
    return f"link:{short_code}"


def stats_cache_key(short_code: str) -> str:
    return f"stats:{short_code}"


def _ttl_seconds(expires_at: datetime | None, default_seconds: int) -> int:
    if not expires_at:
        return default_seconds
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    seconds = int((expires_at - now).total_seconds())
    return max(1, min(default_seconds, seconds))


async def cache_link(
    redis_client,
    *,
    short_code: str,
    original_url: str,
    expires_at: datetime | None,
    default_ttl_seconds: int = 3600,
) -> None:
    payload = {"original_url": original_url, "expires_at": expires_at.isoformat() if expires_at else None}
    await redis_client.setex(
        link_cache_key(short_code),
        _ttl_seconds(expires_at, default_ttl_seconds),
        json.dumps(payload),
    )


async def get_cached_link(redis_client, short_code: str) -> dict | None:
    raw = await redis_client.get(link_cache_key(short_code))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def invalidate_link(redis_client, short_code: str) -> None:
    await redis_client.delete(link_cache_key(short_code), stats_cache_key(short_code))


async def cache_stats(
    redis_client,
    *,
    short_code: str,
    stats: dict,
    ttl_seconds: int = 60,
) -> None:
    await redis_client.setex(stats_cache_key(short_code), ttl_seconds, json.dumps(stats))


async def get_cached_stats(redis_client, short_code: str) -> dict | None:
    raw = await redis_client.get(stats_cache_key(short_code))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

