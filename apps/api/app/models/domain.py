import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    reviewer = "reviewer"
    viewer = "viewer"


class EnrollmentBatchStatus(str, enum.Enum):
    incomplete = "incomplete"
    ready = "ready"
    archived = "archived"


class AttendanceSource(str, enum.Enum):
    ai_confirmed = "ai_confirmed"
    manual_override = "manual_override"


class AttendanceStatus(str, enum.Enum):
    on_time = "on_time"
    late = "late"


class ReviewStatus(str, enum.Enum):
    open = "open"
    approved = "approved"
    rejected = "rejected"
    manual_marked = "manual_marked"


class ReviewReason(str, enum.Enum):
    unknown = "unknown"
    ambiguous = "ambiguous"
    spoof = "spoof"
    multiple_faces = "multiple_faces"


class RecognitionOutcome(str, enum.Enum):
    no_face = "no_face"
    multiple_faces_rejected = "multiple_faces_rejected"
    quality_rejected = "quality_rejected"
    spoof_rejected = "spoof_rejected"
    unknown = "unknown"
    ambiguous = "ambiguous"
    candidate_tracking = "candidate_tracking"
    duplicate = "duplicate"
    attendance_marked = "attendance_marked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    refresh_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    owned_person: Mapped["Person | None"] = relationship(
        back_populates="owner_user",
        uselist=False,
        foreign_keys="Person.owner_user_id",
    )


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))

    owner_user: Mapped["User | None"] = relationship(back_populates="owned_person", foreign_keys=[owner_user_id])
    enrollment_batches: Mapped[list["EnrollmentBatch"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class EnrollmentBatch(Base):
    __tablename__ = "enrollment_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"), nullable=False, index=True)
    status: Mapped[EnrollmentBatchStatus] = mapped_column(
        Enum(EnrollmentBatchStatus, native_enum=False),
        default=EnrollmentBatchStatus.incomplete,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_self_enrollment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bypass_quality_validation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target_sample_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    replacement_for_batch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("enrollment_batches.id"))
    diversity_status: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    quality_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    person: Mapped["Person"] = relationship(back_populates="enrollment_batches")
    samples: Mapped[list["EnrollmentSample"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class EnrollmentSample(Base):
    __tablename__ = "enrollment_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("enrollment_batches.id"), nullable=False, index=True)
    diversity_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capture_index: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512))
    rejection_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    batch: Mapped["EnrollmentBatch"] = relationship(back_populates="samples")
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(back_populates="sample", cascade="all, delete-orphan")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"), nullable=False, index=True)
    sample_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("enrollment_samples.id"))
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    norm: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_centroid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    person: Mapped["Person"] = relationship(back_populates="embeddings")
    sample: Mapped["EnrollmentSample"] = relationship(back_populates="embeddings")


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    late_after_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    review_unknowns: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    review_ambiguous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    allowed_people: Mapped[list["SessionAllowedPerson"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionAllowedPerson(Base):
    __tablename__ = "session_allowed_persons"
    __table_args__ = (UniqueConstraint("session_id", "person_id", name="uq_session_allowed_person"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"), nullable=False, index=True)

    session: Mapped["AttendanceSession"] = relationship(back_populates="allowed_people")


class RecognitionAttempt(Base):
    __tablename__ = "recognition_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    client_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    outcome: Mapped[RecognitionOutcome] = mapped_column(Enum(RecognitionOutcome, native_enum=False), nullable=False)
    face_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    liveness_score: Mapped[float | None] = mapped_column(Float)
    top_person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("persons.id"))
    top_score: Mapped[float | None] = mapped_column(Float)
    second_score: Mapped[float | None] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_path: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"
    __table_args__ = (UniqueConstraint("session_id", "person_id", name="uq_session_person_attendance"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"), nullable=False, index=True)
    source: Mapped[AttendanceSource] = mapped_column(Enum(AttendanceSource, native_enum=False), nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus, native_enum=False), nullable=False)
    recognized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    recognition_attempt_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("recognition_attempts.id"))
    manual_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))


class ReviewCase(Base):
    __tablename__ = "review_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("recognition_attempts.id"), nullable=False, unique=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    reason: Mapped[ReviewReason] = mapped_column(Enum(ReviewReason, native_enum=False), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, native_enum=False), default=ReviewStatus.open, nullable=False)
    proposed_person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("persons.id"))
    resolved_person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("persons.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
