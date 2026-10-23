"""Fixture tests — red until the calc.py bug is patched."""

from calc import add


def test_add() -> None:
    assert add(2, 3) == 5
