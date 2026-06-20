"""add attachment text extraction

Revision ID: 20260620_0010
Revises: 20260620_0009
Create Date: 2026-06-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0010"
down_revision = "20260620_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_attachments", sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "case_attachments",
        sa.Column("extraction_status", sa.String(length=40), nullable=False, server_default="pending"),
    )
    op.create_index(
        op.f("ix_case_attachments_extraction_status"),
        "case_attachments",
        ["extraction_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_case_attachments_extraction_status"), table_name="case_attachments")
    op.drop_column("case_attachments", "extraction_status")
    op.drop_column("case_attachments", "extracted_text")
