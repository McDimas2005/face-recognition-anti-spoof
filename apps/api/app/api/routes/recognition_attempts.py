from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import Person, RecognitionAttempt, UserRole
from app.schemas.common import MessageResponse
from app.schemas.recognition import RecognitionAttemptResponse
from app.services.admin_cleanup import clear_recognition_attempts, delete_recognition_attempt
from app.services.audit import write_audit_log

router = APIRouter()


def _person_name_map(db: Session, person_ids: list[str]) -> dict[str, str]:
    ids = list(dict.fromkeys(person_id for person_id in person_ids if person_id))
    if not ids:
        return {}
    rows = db.execute(select(Person.id, Person.full_name).where(Person.id.in_(ids))).all()
    return {person_id: full_name for person_id, full_name in rows}


@router.get("", response_model=list[RecognitionAttemptResponse])
def list_recognition_attempts(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    attempts = list(db.scalars(select(RecognitionAttempt).order_by(RecognitionAttempt.created_at.desc())).all())
    person_names = _person_name_map(db, [attempt.top_person_id for attempt in attempts if attempt.top_person_id])
    return [
        RecognitionAttemptResponse(
            id=attempt.id,
            session_id=attempt.session_id,
            client_key=attempt.client_key,
            outcome=attempt.outcome,
            face_count=attempt.face_count,
            quality_passed=attempt.quality_passed,
            liveness_score=attempt.liveness_score,
            top_person_id=attempt.top_person_id,
            top_person_name=person_names.get(attempt.top_person_id) or attempt.breakdown.get("top_person_name"),
            top_score=attempt.top_score,
            second_score=attempt.second_score,
            breakdown=attempt.breakdown,
            created_at=attempt.created_at,
        )
        for attempt in attempts
    ]


@router.delete("", response_model=MessageResponse)
def clear_recognition_attempts_route(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> MessageResponse:
    clear_recognition_attempts(db)
    write_audit_log(db, actor.id, "recognition_attempt", "all", "recognition_attempts_cleared", {})
    db.commit()
    return MessageResponse(message="Recognition attempts cleared")


@router.delete("/{attempt_id}", response_model=MessageResponse)
def delete_recognition_attempt_route(
    attempt_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> MessageResponse:
    attempt = db.get(RecognitionAttempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Recognition attempt not found")
    attempt_details = {"outcome": attempt.outcome.value}
    delete_recognition_attempt(db, attempt)
    write_audit_log(db, actor.id, "recognition_attempt", attempt_id, "recognition_attempt_deleted", attempt_details)
    db.commit()
    return MessageResponse(message="Recognition attempt deleted")
