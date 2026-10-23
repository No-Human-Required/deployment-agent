"""Guardrails: pytest must never target the live companion database."""

from __future__ import annotations

import pytest

from tests.conftest import _assert_safe_test_database, _database_name


def test_live_companion_name_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="protected database"):
        _assert_safe_test_database(
            "postgresql://liara:liara@localhost:5433/liara_companion"
        )


def test_test_database_name_is_accepted() -> None:
    assert (
        _assert_safe_test_database(
            "postgresql://liara:liara@localhost:5433/liara_companion_test"
        )
        == "liara_companion_test"
    )


def test_database_name_parser() -> None:
    assert _database_name("postgresql://x@h:5433/liara_companion") == "liara_companion"
    assert _database_name("postgresql://x@h/foo_test?sslmode=disable") == "foo_test"
