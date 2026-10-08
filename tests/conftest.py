"""Shared fixtures. The doubles themselves live in ``tests.doubles``."""

from __future__ import annotations

import pytest

from tests.doubles import FakeCellar


@pytest.fixture
def cellar() -> FakeCellar:
    return FakeCellar()


@pytest.fixture
def sleeps() -> list[float]:
    return []
