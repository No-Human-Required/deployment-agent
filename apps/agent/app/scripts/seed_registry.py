"""Seed capability catalog (idempotent).

Usage (from apps/agent):
  uv run python -m app.scripts.seed_registry
"""

from __future__ import annotations

from app.db.session import get_session_factory
from app.services.registry import CapabilityRegistry


def main() -> None:
    factory = get_session_factory()
    with factory() as session:
        registry = CapabilityRegistry(session)
        inserted = registry.seed()
        session.commit()
        print(f"capability seed complete; inserted={inserted}")


if __name__ == "__main__":
    main()
