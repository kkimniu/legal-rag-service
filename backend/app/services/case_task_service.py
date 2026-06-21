from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.legal_case import CaseTask, LegalCase


def list_case_tasks(db: Session, case_id: int, limit: int = 100) -> list[CaseTask]:
    """Return incomplete and near-due tasks first for one legal matter."""
    tasks = list(db.scalars(select(CaseTask).where(CaseTask.case_id == case_id)))
    tasks.sort(
        key=lambda task: (
            task.is_completed,
            task.due_date is None,
            task.due_date or date.max,
            task.created_at,
        )
    )
    return tasks[:limit]


def get_case_task(db: Session, case_id: int, task_id: int) -> CaseTask | None:
    statement = select(CaseTask).where(CaseTask.id == task_id, CaseTask.case_id == case_id)
    return db.scalar(statement)


def create_case_task(
    db: Session,
    legal_case: LegalCase,
    title: str,
    due_date: date | None,
) -> CaseTask:
    task = CaseTask(case_id=legal_case.id, title=title.strip(), due_date=due_date)
    legal_case.updated_at = datetime.now(UTC)
    db.add(task)
    db.add(legal_case)
    db.commit()
    db.refresh(task)
    return task


def update_case_task(
    db: Session,
    legal_case: LegalCase,
    task: CaseTask,
    title: str,
    due_date: date | None,
    is_completed: bool,
) -> CaseTask:
    task.title = title.strip()
    task.due_date = due_date
    task.is_completed = is_completed
    task.updated_at = datetime.now(UTC)
    legal_case.updated_at = task.updated_at
    db.add(task)
    db.add(legal_case)
    db.commit()
    db.refresh(task)
    return task


def delete_case_task(db: Session, legal_case: LegalCase, task: CaseTask) -> None:
    legal_case.updated_at = datetime.now(UTC)
    db.delete(task)
    db.add(legal_case)
    db.commit()
