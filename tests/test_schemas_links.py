"""Тесты схем links: валидаторы expires_at и т.д."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.links import LinkCreate, LinkUpdate


def test_link_create_expires_at_minute_precision_rejected():
    """expires_at с секундами — ValidationError."""
    with pytest.raises(ValueError, match="minute precision"):
        LinkCreate(
            original_url="https://example.com",
            expires_at=datetime(2030, 1, 1, 10, 30, 5, tzinfo=timezone.utc),
        )


def test_link_create_expires_at_past_rejected():
    """expires_at в прошлом — ValidationError."""
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(second=0, microsecond=0)
    with pytest.raises(ValueError, match="future"):
        LinkCreate(original_url="https://example.com", expires_at=past)


def test_link_create_expires_at_future_ok():
    """expires_at в будущем с точностью до минуты — ок."""
    future = (datetime.now(timezone.utc) + timedelta(days=1)).replace(second=0, microsecond=0)
    m = LinkCreate(original_url="https://example.com", expires_at=future)
    assert m.expires_at == future


def test_link_create_expires_at_none_ok():
    """expires_at None — ок."""
    m = LinkCreate(original_url="https://example.com")
    assert m.expires_at is None


def test_link_update_expires_at_seconds_rejected():
    with pytest.raises(ValueError, match="minute precision"):
        LinkUpdate(expires_at=datetime(2030, 1, 1, 10, 30, 5, tzinfo=timezone.utc))


def test_link_update_expires_at_past_rejected():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(second=0, microsecond=0)
    with pytest.raises(ValueError, match="future"):
        LinkUpdate(expires_at=past)


def test_link_update_expires_at_future_ok():
    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(second=0, microsecond=0)
    m = LinkUpdate(expires_at=future)
    assert m.expires_at == future


def test_link_update_expires_at_naive_treated_as_utc():
    future_naive = (datetime.utcnow() + timedelta(days=1)).replace(second=0, microsecond=0)
    m = LinkUpdate(expires_at=future_naive)
    assert m.expires_at is not None
