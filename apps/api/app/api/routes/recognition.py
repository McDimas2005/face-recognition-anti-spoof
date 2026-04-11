from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import Person, UserRole
from app.schemas.recognition import RecognitionResponse
from app.services.recognition import evaluate_frame

router = APIRouter()


@router.post("/evaluate", response_model=RecognitionResponse)
def evaluate(
    session_id: str = Form(...),
    client_key: str = Form(...),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
) -> RecognitionResponse:
    result = evaluate_frame(db, session_id=session_id, client_key=client_key, upload=frame, actor_user_id=actor.id)
    db.commit()
    attempt = result["attempt"]
    attendance_event = result.get("attendance_event")
    top_person = db.get(Person, attempt.top_person_id) if attempt.top_person_id else None
    return RecognitionResponse(
        attempt_id=attempt.id,
        state=attempt.outcome,
        top_person_id=attempt.top_person_id,
        top_person_name=top_person.full_name if top_person else attempt.breakdown.get("top_person_name"),
        top_score=attempt.top_score,
        second_score=attempt.second_score,
        liveness_score=attempt.liveness_score,
        face_count=attempt.face_count,
        breakdown=attempt.breakdown,
        attendance_event_id=attendance_event.id if attendance_event else None,
    )
