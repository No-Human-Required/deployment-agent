"""Workspace settings for Liara + Aval AI.

Revision ID: 20261022_0002
Revises: 20261022_0001
Create Date: 2026-10-22

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0002"
down_revision: Union[str, Sequence[str], None] = "20261022_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "liara_api_base_url",
            sa.String(length=512),
            nullable=False,
            server_default="https://api.liara.ir",
        ),
        sa.Column("liara_team_id", sa.String(length=255), nullable=True),
        sa.Column("llm_base_url", sa.String(length=512), nullable=True),
        sa.Column("llm_model", sa.String(length=255), nullable=True),
        sa.Column(
            "liara_token_secret_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "llm_api_key_secret_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["liara_token_secret_id"], ["secret_refs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["llm_api_key_secret_id"], ["secret_refs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        "ix_workspace_settings_workspace_id",
        "workspace_settings",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_settings_workspace_id", table_name="workspace_settings"
    )
    op.drop_table("workspace_settings")
