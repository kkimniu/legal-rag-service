"""create case tasks

Revision ID: 20260621_0012
Revises: 20260621_0011
Create Date: 2026-06-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260621_0012"
down_revision = "20260621_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_tasks_id"), "case_tasks", ["id"], unique=False)
    op.create_index(op.f("ix_case_tasks_case_id"), "case_tasks", ["case_id"], unique=False)
    op.create_index(op.f("ix_case_tasks_due_date"), "case_tasks", ["due_date"], unique=False)
    op.create_index(op.f("ix_case_tasks_is_completed"), "case_tasks", ["is_completed"], unique=False)
    op.create_index(op.f("ix_case_tasks_created_at"), "case_tasks", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_case_tasks_created_at"), table_name="case_tasks")
    op.drop_index(op.f("ix_case_tasks_is_completed"), table_name="case_tasks")
    op.drop_index(op.f("ix_case_tasks_due_date"), table_name="case_tasks")
    op.drop_index(op.f("ix_case_tasks_case_id"), table_name="case_tasks")
    op.drop_index(op.f("ix_case_tasks_id"), table_name="case_tasks")
    op.drop_table("case_tasks")
