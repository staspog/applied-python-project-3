"""Юнит-тесты: логика сервиса ссылок (срок истечения и т.п.)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.links import _is_expired


def test_is_expired_none():
    """Нет даты истечения — не истекла."""
    assert _is_expired(None) is False


def test_is_expired_past():
    """Дата в прошлом — истекла."""
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert _is_expired(past) is True


def test_is_expired_future():
    """Дата в будущем — не истекла."""
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert _is_expired(future) is False


def test_is_expired_naive_datetime():
    """Наивная datetime без tz обрабатывается как UTC."""
    past_naive = datetime.utcnow() - timedelta(seconds=10)
    assert _is_expired(past_naive) is True
