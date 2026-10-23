"""Phase-6 maintain: monitors, incidents, recovery baselines, workspace members.

Revision ID: 20261022_0004
Revises: 20261022_0003
Create Date: 2026-10-22

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0004"
down_revision: Union[str, Sequence[str], None] = "20261022_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "actor_id",
            name="uq_workspace_members_workspace_actor",
        ),
    )
    op.create_index(
        "ix_workspace_members_workspace_id",
        "workspace_members",
        ["workspace_id"],
    )

    op.create_table(
        "monitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=True),
        sa.Column("notification_allowed", sa.Boolean(), nullable=False),
        sa.Column("last_status", sa.String(length=64), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_data_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_misses", sa.Integer(), nullable=False),
        sa.Column("grants_write_permission", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_monitors_workspace_id", "monitors", ["workspace_id"])
    op.create_index("ix_monitors_case_id", "monitors", ["case_id"])

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "monitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("alert_count", sa.Integer(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("write_authorized", sa.Boolean(), nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolve_evidence", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "dedupe_key",
            name="uq_incidents_workspace_dedupe",
        ),
    )
    op.create_index("ix_incidents_workspace_id", "incidents", ["workspace_id"])
    op.create_index("ix_incidents_monitor_id", "incidents", ["monitor_id"])
    op.create_index("ix_incidents_case_id", "incidents", ["case_id"])

    op.create_table(
        "recovery_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "source_operation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_recovery_baselines_workspace_id",
        "recovery_baselines",
        ["workspace_id"],
    )
    op.create_index(
        "ix_recovery_baselines_case_id",
        "recovery_baselines",
        ["case_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recovery_baselines_case_id", table_name="recovery_baselines")
    op.drop_index(
        "ix_recovery_baselines_workspace_id", table_name="recovery_baselines"
    )
    op.drop_table("recovery_baselines")
    op.drop_index("ix_incidents_case_id", table_name="incidents")
    op.drop_index("ix_incidents_monitor_id", table_name="incidents")
    op.drop_index("ix_incidents_workspace_id", table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_monitors_case_id", table_name="monitors")
    op.drop_index("ix_monitors_workspace_id", table_name="monitors")
    op.drop_table("monitors")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")
