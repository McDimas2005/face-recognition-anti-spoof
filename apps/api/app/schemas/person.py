from datetime import datetime

from pydantic import BaseModel

from app.models.domain import EnrollmentBatchStatus


class PersonCreate(BaseModel):
    full_name: str
    external_id: str | None = None
    notes: str | None = None


class PersonUpdate(BaseModel):
    full_name: str | None = None
    external_id: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class PersonResponse(BaseModel):
    id: str
    full_name: str
    external_id: str | None
    notes: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EnrollmentBatchCreate(BaseModel):
    person_id: str


class EnrollmentBatchResponse(BaseModel):
    id: str
    person_id: str
    status: EnrollmentBatchStatus
    diversity_status: dict
    quality_summary: dict
    created_at: datetime

    class Config:
        from_attributes = True


class EnrollmentSampleResponse(BaseModel):
    id: str
    batch_id: str
    diversity_tag: str
    quality_passed: bool
    quality_score: float
    metadata_json: dict
    rejection_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True

