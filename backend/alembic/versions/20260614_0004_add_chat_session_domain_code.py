"""add chat session domain code

Revision ID: 20260614_0004
Revises: 20260614_0003
Create Date: 2026-06-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260614_0004"
down_revision = "20260614_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("domain_code", sa.String(length=80), nullable=True))
    op.create_index(op.f("ix_chat_sessions_domain_code"), "chat_sessions", ["domain_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_sessions_domain_code"), table_name="chat_sessions")
    op.drop_column("chat_sessions", "domain_code")
