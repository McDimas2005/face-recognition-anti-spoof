from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import AttendanceEvent, Person, RecognitionAttempt, UserRole
from app.schemas.common import MessageResponse
from app.schemas.recognition import AttendanceEventResponse, RecognitionAttemptResponse
from app.services.audit import write_audit_log

router = APIRouter()


def _person_name_map(db: Session, person_ids: list[str]) -> dict[str, str]:
    ids = list(dict.fromkeys(person_id for person_id in person_ids if person_id))
    if not ids:
        return {}
    rows = db.execute(select(Person.id, Person.full_name).where(Person.id.in_(ids))).all()
    return {person_id: full_name for person_id, full_name in rows}


@router.get("", response_model=list[AttendanceEventResponse])
def list_attendance_events(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    events = list(db.scalars(select(AttendanceEvent).order_by(AttendanceEvent.recognized_at.desc())).all())
    person_names = _person_name_map(db, [event.person_id for event in events])
    return [
        AttendanceEventResponse(
            id=event.id,
            session_id=event.session_id,
            person_id=event.person_id,
            person_name=person_names.get(event.person_id),
            source=event.source,
            status=event.status,
            recognized_at=event.recognized_at,
            manual_reason=event.manual_reason,
        )
        for event in events
    ]


@router.get("/attempts", response_model=list[RecognitionAttemptResponse])
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
def clear_attendance_events(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> MessageResponse:
    db.execute(delete(AttendanceEvent))
    write_audit_log(db, actor.id, "attendance_event", "all", "attendance_events_cleared", {})
    db.commit()
    return MessageResponse(message="Attendance events cleared")


@router.delete("/{event_id}", response_model=MessageResponse)
def delete_attendance_event(
    event_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> MessageResponse:
    event = db.get(AttendanceEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Attendance event not found")
    event_details = {"person_id": event.person_id, "session_id": event.session_id}
    db.delete(event)
    write_audit_log(db, actor.id, "attendance_event", event_id, "attendance_event_deleted", event_details)
    db.commit()
    return MessageResponse(message="Attendance event deleted")
