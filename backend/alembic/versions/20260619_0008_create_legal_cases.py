"""create legal cases

Revision ID: 20260619_0008
Revises: 20260619_0007
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260619_0008"
down_revision = "20260619_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("domain_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_legal_cases_id"), "legal_cases", ["id"], unique=False)
    op.create_index(op.f("ix_legal_cases_user_id"), "legal_cases", ["user_id"], unique=False)
    op.create_index(op.f("ix_legal_cases_status"), "legal_cases", ["status"], unique=False)
    op.create_index(op.f("ix_legal_cases_domain_code"), "legal_cases", ["domain_code"], unique=False)
    op.create_index(op.f("ix_legal_cases_created_at"), "legal_cases", ["created_at"], unique=False)
    op.create_index(op.f("ix_legal_cases_updated_at"), "legal_cases", ["updated_at"], unique=False)

    op.create_table(
        "case_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="메모"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_notes_id"), "case_notes", ["id"], unique=False)
    op.create_index(op.f("ix_case_notes_case_id"), "case_notes", ["case_id"], unique=False)
    op.create_index(op.f("ix_case_notes_created_at"), "case_notes", ["created_at"], unique=False)
    op.create_index(op.f("ix_case_notes_updated_at"), "case_notes", ["updated_at"], unique=False)

    op.add_column("chat_sessions", sa.Column("case_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_chat_sessions_case_id_legal_cases",
        "chat_sessions",
        "legal_cases",
        ["case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_chat_sessions_case_id"), "chat_sessions", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_sessions_case_id"), table_name="chat_sessions")
    op.drop_constraint("fk_chat_sessions_case_id_legal_cases", "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "case_id")
    op.drop_index(op.f("ix_case_notes_updated_at"), table_name="case_notes")
    op.drop_index(op.f("ix_case_notes_created_at"), table_name="case_notes")
    op.drop_index(op.f("ix_case_notes_case_id"), table_name="case_notes")
    op.drop_index(op.f("ix_case_notes_id"), table_name="case_notes")
    op.drop_table("case_notes")
    op.drop_index(op.f("ix_legal_cases_updated_at"), table_name="legal_cases")
    op.drop_index(op.f("ix_legal_cases_created_at"), table_name="legal_cases")
    op.drop_index(op.f("ix_legal_cases_domain_code"), table_name="legal_cases")
    op.drop_index(op.f("ix_legal_cases_status"), table_name="legal_cases")
    op.drop_index(op.f("ix_legal_cases_user_id"), table_name="legal_cases")
    op.drop_index(op.f("ix_legal_cases_id"), table_name="legal_cases")
    op.drop_table("legal_cases")
