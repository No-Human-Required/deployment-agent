"""Fixture app with a deliberate arithmetic bug for phase-5 patch tests."""


def add(a: int, b: int) -> int:
    # Intentional bug: subtract instead of add (fixed by sandbox patch).
    return a - b
