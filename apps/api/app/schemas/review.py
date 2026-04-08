from datetime import datetime

from pydantic import BaseModel

from app.models.domain import ReviewReason, ReviewStatus


class ReviewCaseResponse(BaseModel):
    id: str
    attempt_id: str
    session_id: str
    reason: ReviewReason
    status: ReviewStatus
    proposed_person_id: str | None
    resolved_person_id: str | None
    resolution_notes: str | None
    resolved_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewResolveRequest(BaseModel):
    action: str
    resolved_person_id: str | None = None
    notes: str | None = None

