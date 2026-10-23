"""Workspace + Case persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.workspace import Workspace


def test_create_case_under_workspace(db_session: Session, workspace: Workspace) -> None:
    case = Case(
        workspace_id=workspace.id,
        goal="Deploy a Node app to Liara",
        constraints={"region": "iran-1"},
        result_criteria={"health": "200"},
        next_owner="operator",
        status="open",
    )
    db_session.add(case)
    db_session.flush()

    loaded = db_session.scalar(select(Case).where(Case.id == case.id))
    assert loaded is not None
    assert loaded.workspace_id == workspace.id
    assert loaded.goal == "Deploy a Node app to Liara"
    assert loaded.constraints == {"region": "iran-1"}
    assert loaded.result_criteria == {"health": "200"}
    assert loaded.next_owner == "operator"

    ws = db_session.get(Workspace, workspace.id)
    assert ws is not None
    assert any(c.id == case.id for c in ws.cases)
