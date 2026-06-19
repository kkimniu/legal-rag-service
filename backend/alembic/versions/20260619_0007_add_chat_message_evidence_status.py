"""add chat message evidence status

Revision ID: 20260619_0007
Revises: 20260619_0006
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260619_0007"
down_revision = "20260619_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("evidence_status", sa.String(length=40), nullable=True))
    op.add_column("chat_messages", sa.Column("evidence_warnings", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_chat_messages_evidence_status"), "chat_messages", ["evidence_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_evidence_status"), table_name="chat_messages")
    op.drop_column("chat_messages", "evidence_warnings")
    op.drop_column("chat_messages", "evidence_status")
