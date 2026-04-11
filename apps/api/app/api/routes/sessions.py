from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import AttendanceSession, SessionAllowedPerson, UserRole
from app.schemas.common import MessageResponse
from app.schemas.session import AttendanceSessionCreate, AttendanceSessionResponse, AttendanceSessionUpdate
from app.services.admin_cleanup import delete_session_graph
from app.services.audit import write_audit_log

router = APIRouter()


def _to_response(session: AttendanceSession) -> AttendanceSessionResponse:
    return AttendanceSessionResponse(
        id=session.id,
        name=session.name,
        description=session.description,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        late_after_minutes=session.late_after_minutes,
        review_unknowns=session.review_unknowns,
        review_ambiguous=session.review_ambiguous,
        status=session.status,
        created_at=session.created_at,
        allowed_person_ids=[item.person_id for item in session.allowed_people],
    )


@router.get("", response_model=list[AttendanceSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    sessions = db.scalars(select(AttendanceSession).options(selectinload(AttendanceSession.allowed_people))).all()
    return [_to_response(item) for item in sessions]


@router.post("", response_model=AttendanceSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
):
    session = AttendanceSession(
        name=payload.name,
        description=payload.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        late_after_minutes=payload.late_after_minutes,
        review_unknowns=payload.review_unknowns,
        review_ambiguous=payload.review_ambiguous,
        created_by=actor.id,
    )
    db.add(session)
    db.flush()
    for person_id in payload.allowed_person_ids:
        db.add(SessionAllowedPerson(session_id=session.id, person_id=person_id))
    db.flush()
    db.refresh(session)
    write_audit_log(db, actor.id, "attendance_session", session.id, "session_created", jsonable_encoder(payload))
    db.commit()
    db.refresh(session)
    return _to_response(session)


@router.delete("/{session_id}", response_model=MessageResponse)
def delete_session_route(
    session_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> MessageResponse:
    session = db.scalar(select(AttendanceSession).where(AttendanceSession.id == session_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session_details = {"name": session.name}
    delete_session_graph(db, session)
    write_audit_log(db, actor.id, "attendance_session", session_id, "session_deleted", session_details)
    db.commit()
    return MessageResponse(message="Session deleted")


@router.patch("/{session_id}", response_model=AttendanceSessionResponse)
def update_session(
    session_id: str,
    payload: AttendanceSessionUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
):
    session = db.scalar(select(AttendanceSession).where(AttendanceSession.id == session_id).options(selectinload(AttendanceSession.allowed_people)))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    data = payload.model_dump(exclude_unset=True)
    allowed_person_ids = data.pop("allowed_person_ids", None)
    for key, value in data.items():
        setattr(session, key, value)
    if allowed_person_ids is not None:
        db.execute(delete(SessionAllowedPerson).where(SessionAllowedPerson.session_id == session_id))
        for person_id in allowed_person_ids:
            db.add(SessionAllowedPerson(session_id=session.id, person_id=person_id))
        db.flush()
        db.refresh(session)
    write_audit_log(
        db,
        actor.id,
        "attendance_session",
        session.id,
        "session_updated",
        jsonable_encoder(payload, exclude_none=True),
    )
    db.commit()
    db.refresh(session)
    return _to_response(session)
