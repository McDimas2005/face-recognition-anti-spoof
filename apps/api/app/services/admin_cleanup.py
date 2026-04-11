from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.domain import (
    AppSetting,
    AttendanceEvent,
    AttendanceSession,
    AuditLog,
    EnrollmentBatch,
    Person,
    RecognitionAttempt,
    ReviewCase,
    SessionAllowedPerson,
    User,
    UserRole,
)


def ensure_user_can_be_deleted(db: Session, actor: User, user: User) -> None:
    if actor.id == user.id:
        raise ValueError("You cannot delete the currently logged-in user")
    if user.role == UserRole.superadmin:
        superadmin_count = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.superadmin)) or 0
        if superadmin_count <= 1:
            raise ValueError("At least one superadmin must remain")


def delete_user_graph(db: Session, user: User) -> None:
    db.execute(update(Person).where(Person.owner_user_id == user.id).values(owner_user_id=None))
    db.execute(update(Person).where(Person.created_by == user.id).values(created_by=None))
    db.execute(update(EnrollmentBatch).where(EnrollmentBatch.created_by == user.id).values(created_by=None))
    db.execute(update(AttendanceSession).where(AttendanceSession.created_by == user.id).values(created_by=None))
    db.execute(update(AttendanceEvent).where(AttendanceEvent.created_by == user.id).values(created_by=None))
    db.execute(update(ReviewCase).where(ReviewCase.resolved_by == user.id).values(resolved_by=None))
    db.execute(update(AppSetting).where(AppSetting.updated_by == user.id).values(updated_by=None))
    db.execute(update(AuditLog).where(AuditLog.actor_user_id == user.id).values(actor_user_id=None))
    db.delete(user)


def delete_person_graph(db: Session, person: Person) -> None:
    db.execute(update(RecognitionAttempt).where(RecognitionAttempt.top_person_id == person.id).values(top_person_id=None))
    db.execute(update(ReviewCase).where(ReviewCase.proposed_person_id == person.id).values(proposed_person_id=None))
    db.execute(update(ReviewCase).where(ReviewCase.resolved_person_id == person.id).values(resolved_person_id=None))
    db.execute(delete(SessionAllowedPerson).where(SessionAllowedPerson.person_id == person.id))
    db.execute(delete(AttendanceEvent).where(AttendanceEvent.person_id == person.id))
    db.delete(person)


def delete_session_graph(db: Session, session: AttendanceSession) -> None:
    db.execute(delete(AttendanceEvent).where(AttendanceEvent.session_id == session.id))
    db.execute(delete(ReviewCase).where(ReviewCase.session_id == session.id))
    db.execute(delete(RecognitionAttempt).where(RecognitionAttempt.session_id == session.id))
    db.execute(delete(SessionAllowedPerson).where(SessionAllowedPerson.session_id == session.id))
    db.delete(session)


def delete_recognition_attempt(db: Session, attempt: RecognitionAttempt) -> None:
    db.execute(update(AttendanceEvent).where(AttendanceEvent.recognition_attempt_id == attempt.id).values(recognition_attempt_id=None))
    db.execute(delete(ReviewCase).where(ReviewCase.attempt_id == attempt.id))
    db.delete(attempt)


def clear_recognition_attempts(db: Session) -> None:
    db.execute(update(AttendanceEvent).where(AttendanceEvent.recognition_attempt_id.is_not(None)).values(recognition_attempt_id=None))
    db.execute(delete(ReviewCase))
    db.execute(delete(RecognitionAttempt))


def clear_attendance_events(db: Session) -> None:
    db.execute(delete(AttendanceEvent))


def clear_review_cases(db: Session) -> None:
    db.execute(delete(ReviewCase))
