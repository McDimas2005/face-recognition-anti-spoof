from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models.domain import AttendanceEvent, Person, RecognitionAttempt, ReviewCase

router = APIRouter()
APP_VERSION = "0.1.0"


def database_status() -> str:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"


def health_payload() -> dict[str, str]:
    db_status = database_status()
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": APP_VERSION,
        "database": db_status,
    }


@router.get("/health")
def health() -> dict[str, str]:
    return health_payload()


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@router.get("/health/ready")
def ready() -> dict[str, str]:
    payload = health_payload()
    return {**payload, "status": "ready" if payload["database"] == "ok" else "degraded"}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "people_total": db.scalar(select(func.count()).select_from(Person)) or 0,
        "recognition_attempts_total": db.scalar(select(func.count()).select_from(RecognitionAttempt)) or 0,
        "attendance_events_total": db.scalar(select(func.count()).select_from(AttendanceEvent)) or 0,
        "review_cases_total": db.scalar(select(func.count()).select_from(ReviewCase)) or 0,
    }
