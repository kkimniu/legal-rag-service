"""add attachment vector status

Revision ID: 20260621_0011
Revises: 20260620_0010
Create Date: 2026-06-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260621_0011"
down_revision = "20260620_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_attachments",
        sa.Column("vector_status", sa.String(length=40), nullable=False, server_default="pending"),
    )
    op.add_column(
        "case_attachments",
        sa.Column("vector_chunk_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        op.f("ix_case_attachments_vector_status"),
        "case_attachments",
        ["vector_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_case_attachments_vector_status"), table_name="case_attachments")
    op.drop_column("case_attachments", "vector_chunk_count")
    op.drop_column("case_attachments", "vector_status")
