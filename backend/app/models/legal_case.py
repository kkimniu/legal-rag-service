from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class LegalCase(Base):
    """Personal legal matter used to group chats, notes, and evidence."""

    __tablename__ = "legal_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    domain_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    notes: Mapped[list["CaseNote"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attachments: Mapped[list["CaseAttachment"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list["CaseTask"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CaseNote(Base):
    """Free-form note attached to one personal legal matter."""

    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("legal_cases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="메모")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    case: Mapped[LegalCase] = relationship(back_populates="notes")


class CaseAttachment(Base):
    """Uploaded file metadata attached to one personal legal matter."""

    __tablename__ = "case_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("legal_cases.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(default=0)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extraction_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    vector_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    vector_chunk_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    case: Mapped[LegalCase] = relationship(back_populates="attachments")


class CaseTask(Base):
    """Action item or deadline tracked under one personal legal matter."""

    __tablename__ = "case_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("legal_cases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case: Mapped[LegalCase] = relationship(back_populates="tasks")
