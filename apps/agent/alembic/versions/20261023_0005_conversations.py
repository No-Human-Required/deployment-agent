"""Conversation threads + workspace folders (Postgres persistence).

Revision ID: 20261023_0005
Revises: 20261022_0004
Create Date: 2026-10-23

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0005"
down_revision: Union[str, Sequence[str], None] = "20261022_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "path", name="uq_workspace_folders_workspace_path"
        ),
    )
    op.create_index(
        "ix_workspace_folders_workspace_id",
        "workspace_folders",
        ["workspace_id"],
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_key", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "service_id",
            sa.String(length=255),
            nullable=False,
            server_default="workspace",
        ),
        sa.Column("context_services", postgresql.JSONB(), nullable=True),
        sa.Column("messages", postgresql.JSONB(), nullable=True),
        sa.Column("orchestrator_run", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_conversations_workspace_id"
        ),
    )
    op.create_index(
        "ix_conversations_workspace_id",
        "conversations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_conversations_folder_key",
        "conversations",
        ["folder_key"],
    )
    op.create_index(
        "ix_conversations_workspace_folder",
        "conversations",
        ["workspace_id", "folder_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_workspace_folder", table_name="conversations")
    op.drop_index("ix_conversations_folder_key", table_name="conversations")
    op.drop_index("ix_conversations_workspace_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_workspace_folders_workspace_id", table_name="workspace_folders")
    op.drop_table("workspace_folders")
