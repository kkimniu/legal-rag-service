"""create rag queries table

Revision ID: 20260531_0002
Revises: 20260531_0001
Create Date: 2026-05-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260531_0002"
down_revision = "20260531_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rag_queries_created_at"), "rag_queries", ["created_at"], unique=False)
    op.create_index(op.f("ix_rag_queries_id"), "rag_queries", ["id"], unique=False)
    op.create_index(op.f("ix_rag_queries_user_id"), "rag_queries", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rag_queries_user_id"), table_name="rag_queries")
    op.drop_index(op.f("ix_rag_queries_id"), table_name="rag_queries")
    op.drop_index(op.f("ix_rag_queries_created_at"), table_name="rag_queries")
    op.drop_table("rag_queries")
