"""create case attachments

Revision ID: 20260620_0009
Revises: 20260619_0008
Create Date: 2026-06-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0009"
down_revision = "20260619_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_attachments_id"), "case_attachments", ["id"], unique=False)
    op.create_index(op.f("ix_case_attachments_case_id"), "case_attachments", ["case_id"], unique=False)
    op.create_index(op.f("ix_case_attachments_created_at"), "case_attachments", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_case_attachments_created_at"), table_name="case_attachments")
    op.drop_index(op.f("ix_case_attachments_case_id"), table_name="case_attachments")
    op.drop_index(op.f("ix_case_attachments_id"), table_name="case_attachments")
    op.drop_table("case_attachments")
