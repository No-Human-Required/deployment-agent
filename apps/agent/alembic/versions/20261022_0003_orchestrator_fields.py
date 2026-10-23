"""Orchestrator fields: approval hash/expiry, operation client_request_id.

Revision ID: 20261022_0003
Revises: 20261022_0002
Create Date: 2026-10-22

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0003"
down_revision: Union[str, Sequence[str], None] = "20261022_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("plan_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "operations",
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_operations_workspace_client_request",
        "operations",
        ["workspace_id", "client_request_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_operations_workspace_client_request",
        "operations",
        type_="unique",
    )
    op.drop_column("operations", "client_request_id")
    op.drop_column("approvals", "expires_at")
    op.drop_column("approvals", "plan_hash")
