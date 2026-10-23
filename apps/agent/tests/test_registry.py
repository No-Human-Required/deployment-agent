"""Capability registry seed and status transitions."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.services.registry import (
    SEED_CATALOG,
    CapabilityRegistry,
    InvalidCapabilityTransition,
)


def test_seed_and_list(db_session: Session) -> None:
    registry = CapabilityRegistry(db_session)
    inserted = registry.seed()
    assert inserted == len(SEED_CATALOG)
    assert registry.seed() == 0  # idempotent

    all_caps = registry.list_all()
    assert len(all_caps) == len(SEED_CATALOG)

    by_id = {c.tool_id: c for c in all_caps}
    assert by_id["list_get_projects"].status == "documented"
    assert by_id["update_envs"].status == "disabled"  # L-D03 unproven
    assert by_id["create_database"].status == "disabled"  # L-D05 unproven
    assert by_id["create_disk"].status == "disabled"  # L-D05 unproven
    assert by_id["native_rollback"].status == "disabled"
    assert by_id["native_rollback"].permanently_disabled is True
    assert by_id["irnic_payment"].status == "disabled"
    assert by_id["irnic_payment"].permanently_disabled is True

    paas = registry.list_by_service("paas")
    assert all(c.service == "paas" for c in paas)
    assert any(c.tool_id == "create_project" for c in paas)


def test_move_to_tested_without_enabling_writes(db_session: Session) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()

    cap = registry.set_status("list_get_projects", "tested")
    assert cap.status == "tested"
    # Still not enabled — no Liara write path opened by this transition alone.
    assert registry.get("create_project").status == "documented"
    assert registry.get("list_get_projects").status == "tested"


def test_invalid_and_permanent_disabled(db_session: Session) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()

    with pytest.raises(InvalidCapabilityTransition):
        registry.set_status("list_get_projects", "enabled")  # skip tested

    with pytest.raises(InvalidCapabilityTransition):
        registry.set_status("native_rollback", "documented")

    with pytest.raises(InvalidCapabilityTransition):
        registry.set_status("irnic_payment", "tested")
