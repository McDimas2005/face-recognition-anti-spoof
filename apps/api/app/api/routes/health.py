from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.domain import AttendanceEvent, Person, RecognitionAttempt, ReviewCase
from fastapi import Depends

router = APIRouter()


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "people_total": db.scalar(select(func.count()).select_from(Person)) or 0,
        "recognition_attempts_total": db.scalar(select(func.count()).select_from(RecognitionAttempt)) or 0,
        "attendance_events_total": db.scalar(select(func.count()).select_from(AttendanceEvent)) or 0,
        "review_cases_total": db.scalar(select(func.count()).select_from(ReviewCase)) or 0,
    }

