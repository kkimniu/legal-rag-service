"""add chat message answer mode

Revision ID: 20260619_0006
Revises: 20260619_0005
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260619_0006"
down_revision = "20260619_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("answer_mode", sa.String(length=40), nullable=True))
    op.create_index(op.f("ix_chat_messages_answer_mode"), "chat_messages", ["answer_mode"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_answer_mode"), table_name="chat_messages")
    op.drop_column("chat_messages", "answer_mode")
