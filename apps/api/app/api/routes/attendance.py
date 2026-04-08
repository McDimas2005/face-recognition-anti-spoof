from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import AttendanceEvent, RecognitionAttempt, UserRole
from app.schemas.recognition import AttendanceEventResponse, RecognitionAttemptResponse

router = APIRouter()


@router.get("", response_model=list[AttendanceEventResponse])
def list_attendance_events(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    return list(db.scalars(select(AttendanceEvent).order_by(AttendanceEvent.recognized_at.desc())).all())


@router.get("/attempts", response_model=list[RecognitionAttemptResponse])
def list_recognition_attempts(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    return list(db.scalars(select(RecognitionAttempt).order_by(RecognitionAttempt.created_at.desc())).all())

