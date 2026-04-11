from datetime import datetime

from pydantic import BaseModel

from app.models.domain import EnrollmentBatchStatus
from app.schemas.person import EnrollmentSampleResponse


class OwnedPersonSummary(BaseModel):
    id: str
    full_name: str
    owner_user_id: str | None


class SelfEnrollmentBatchSummary(BaseModel):
    id: str
    person_id: str
    status: EnrollmentBatchStatus
    is_active: bool
    is_self_enrollment: bool
    bypass_quality_validation: bool
    target_sample_count: int
    replacement_for_batch_id: str | None
    diversity_status: dict
    quality_summary: dict
    accepted_sample_count: int
    total_sample_count: int
    remaining_sample_count: int
    last_sample_id: str | None
    created_at: datetime
    finalized_at: datetime | None


class SelfEnrollmentStatusResponse(BaseModel):
    person: OwnedPersonSummary
    active_batch: SelfEnrollmentBatchSummary | None
    draft_batch: SelfEnrollmentBatchSummary | None
    quality_bypass_allowed: bool
    target_sample_count: int


class SelfEnrollmentStartRequest(BaseModel):
    bypass_quality_validation: bool = False


class SelfEnrollmentFinalizeRequest(BaseModel):
    batch_id: str
    confirm_replace: bool = False


class SelfEnrollmentStartResponse(BaseModel):
    person: OwnedPersonSummary
    batch: SelfEnrollmentBatchSummary
    created_person: bool


class SelfEnrollmentFrameResponse(BaseModel):
    batch: SelfEnrollmentBatchSummary
    sample: EnrollmentSampleResponse
    accepted: bool
    message: str


class SelfEnrollmentFinalizeResponse(BaseModel):
    batch: SelfEnrollmentBatchSummary
    replaced_batch_id: str | None
    active_sample_count: int


class SelfEnrollmentRetakeResponse(BaseModel):
    batch: SelfEnrollmentBatchSummary
    removed_sample_id: str
