"""Юнит-тесты: генерация короткого кода."""
from __future__ import annotations

import string

import pytest

from app.services.short_code import generate_short_code


def test_generate_short_code_length():
    """Длина по умолчанию 8."""
    code = generate_short_code()
    assert len(code) == 8


def test_generate_short_code_custom_length():
    """Кастомная длина."""
    code = generate_short_code(length=12)
    assert len(code) == 12


def test_generate_short_code_charset():
    """Символы только из букв и цифр (ASCII)."""
    alphabet = set(string.ascii_letters + string.digits)
    for _ in range(50):
        code = generate_short_code(length=10)
        assert set(code) <= alphabet


def test_generate_short_code_uniqueness():
    """Подряд сгенерированные коды различаются (с высокой вероятностью)."""
    codes = [generate_short_code() for _ in range(100)]
    assert len(codes) == len(set(codes))
