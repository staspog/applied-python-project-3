"""Юнит-тесты сервиса cache."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.cache import (
    _ttl_seconds,
    cache_link,
    get_cached_link,
    get_cached_stats,
    link_cache_key,
    stats_cache_key,
)


def test_link_cache_key():
    assert link_cache_key("abc") == "link:abc"


def test_stats_cache_key():
    assert stats_cache_key("xyz") == "stats:xyz"


def test_ttl_seconds_no_expires():
    assert _ttl_seconds(None, 3600) == 3600


def test_ttl_seconds_with_future_expires():
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    s = _ttl_seconds(future, 3600)
    assert 1 <= s <= 3600


def test_ttl_seconds_naive_datetime():
    future = datetime.utcnow() + timedelta(hours=1)
    s = _ttl_seconds(future, 3600)
    assert s >= 1


@pytest.mark.asyncio
async def test_get_cached_link_invalid_json_returns_none():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="{ invalid json")
    result = await get_cached_link(redis, "x")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_stats_invalid_json_returns_none():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="not json")
    result = await get_cached_stats(redis, "y")
    assert result is None
