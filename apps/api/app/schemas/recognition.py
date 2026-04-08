from datetime import datetime

from pydantic import BaseModel

from app.models.domain import RecognitionOutcome


class RecognitionResponse(BaseModel):
    attempt_id: str
    state: RecognitionOutcome
    top_person_id: str | None = None
    top_score: float | None = None
    second_score: float | None = None
    liveness_score: float | None = None
    face_count: int
    breakdown: dict
    attendance_event_id: str | None = None


class RecognitionAttemptResponse(BaseModel):
    id: str
    session_id: str
    client_key: str
    outcome: RecognitionOutcome
    face_count: int
    quality_passed: bool
    liveness_score: float | None
    top_person_id: str | None
    top_score: float | None
    second_score: float | None
    breakdown: dict
    created_at: datetime

    class Config:
        from_attributes = True


class AttendanceEventResponse(BaseModel):
    id: str
    session_id: str
    person_id: str
    source: str
    status: str
    recognized_at: datetime
    manual_reason: str | None

    class Config:
        from_attributes = True

