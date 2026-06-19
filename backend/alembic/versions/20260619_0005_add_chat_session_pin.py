"""add chat session pin flag

Revision ID: 20260619_0005
Revises: 20260614_0004
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260619_0005"
down_revision = "20260614_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_chat_sessions_is_pinned"), "chat_sessions", ["is_pinned"], unique=False)
    op.alter_column("chat_sessions", "is_pinned", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_sessions_is_pinned"), table_name="chat_sessions")
    op.drop_column("chat_sessions", "is_pinned")
