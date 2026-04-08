from datetime import datetime

from pydantic import BaseModel


class AttendanceSessionCreate(BaseModel):
    name: str
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    late_after_minutes: int = 10
    review_unknowns: bool = True
    review_ambiguous: bool = True
    allowed_person_ids: list[str] = []


class AttendanceSessionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    late_after_minutes: int | None = None
    review_unknowns: bool | None = None
    review_ambiguous: bool | None = None
    status: str | None = None
    allowed_person_ids: list[str] | None = None


class AttendanceSessionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    late_after_minutes: int
    review_unknowns: bool
    review_ambiguous: bool
    status: str
    created_at: datetime
    allowed_person_ids: list[str]

