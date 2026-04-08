"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("superadmin", "admin", "reviewer", "viewer", name="userrole", native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("refresh_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "persons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_id", sa.String(length=100)),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("external_id"),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "attendance_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("late_after_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("review_unknowns", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_ambiguous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="scheduled"),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "enrollment_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("incomplete", "ready", "archived", name="enrollmentbatchstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("diversity_status", sa.JSON(), nullable=False),
        sa.Column("quality_summary", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_enrollment_batches_person_id", "enrollment_batches", ["person_id"], unique=False)

    op.create_table(
        "session_allowed_persons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("attendance_sessions.id"), nullable=False),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("persons.id"), nullable=False),
        sa.UniqueConstraint("session_id", "person_id", name="uq_session_allowed_person"),
    )
    op.create_index("ix_session_allowed_persons_session_id", "session_allowed_persons", ["session_id"], unique=False)
    op.create_index("ix_session_allowed_persons_person_id", "session_allowed_persons", ["person_id"], unique=False)

    op.create_table(
        "enrollment_samples",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("enrollment_batches.id"), nullable=False),
        sa.Column("diversity_tag", sa.String(length=50), nullable=False),
        sa.Column("quality_passed", sa.Boolean(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("storage_path", sa.String(length=512)),
        sa.Column("rejection_reason", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_enrollment_samples_batch_id", "enrollment_samples", ["batch_id"], unique=False)

    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("sample_id", sa.String(length=36), sa.ForeignKey("enrollment_samples.id")),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("norm", sa.Float(), nullable=False),
        sa.Column("is_centroid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_face_embeddings_person_id", "face_embeddings", ["person_id"], unique=False)

    op.create_table(
        "recognition_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("attendance_sessions.id"), nullable=False),
        sa.Column("client_key", sa.String(length=120), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "no_face",
                "multiple_faces_rejected",
                "quality_rejected",
                "spoof_rejected",
                "unknown",
                "ambiguous",
                "candidate_tracking",
                "duplicate",
                "attendance_marked",
                name="recognitionoutcome",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("face_count", sa.Integer(), nullable=False),
        sa.Column("quality_passed", sa.Boolean(), nullable=False),
        sa.Column("liveness_score", sa.Float()),
        sa.Column("top_person_id", sa.String(length=36), sa.ForeignKey("persons.id")),
        sa.Column("top_score", sa.Float()),
        sa.Column("second_score", sa.Float()),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("snapshot_path", sa.String(length=512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recognition_attempts_session_id", "recognition_attempts", ["session_id"], unique=False)
    op.create_index("ix_recognition_attempts_client_key", "recognition_attempts", ["client_key"], unique=False)

    op.create_table(
        "attendance_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("attendance_sessions.id"), nullable=False),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("source", sa.Enum("ai_confirmed", "manual_override", name="attendancesource", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("on_time", "late", name="attendancestatus", native_enum=False), nullable=False),
        sa.Column("recognized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recognition_attempt_id", sa.String(length=36), sa.ForeignKey("recognition_attempts.id")),
        sa.Column("manual_reason", sa.Text()),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("session_id", "person_id", name="uq_session_person_attendance"),
    )
    op.create_index("ix_attendance_events_session_id", "attendance_events", ["session_id"], unique=False)
    op.create_index("ix_attendance_events_person_id", "attendance_events", ["person_id"], unique=False)

    op.create_table(
        "review_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("attempt_id", sa.String(length=36), sa.ForeignKey("recognition_attempts.id"), nullable=False, unique=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("attendance_sessions.id"), nullable=False),
        sa.Column("reason", sa.Enum("unknown", "ambiguous", "spoof", "multiple_faces", name="reviewreason", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("open", "approved", "rejected", "manual_marked", name="reviewstatus", native_enum=False), nullable=False),
        sa.Column("proposed_person_id", sa.String(length=36), sa.ForeignKey("persons.id")),
        sa.Column("resolved_person_id", sa.String(length=36), sa.ForeignKey("persons.id")),
        sa.Column("resolution_notes", sa.Text()),
        sa.Column("resolved_by", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_cases_session_id", "review_cases", ["session_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_review_cases_session_id", table_name="review_cases")
    op.drop_table("review_cases")
    op.drop_index("ix_attendance_events_person_id", table_name="attendance_events")
    op.drop_index("ix_attendance_events_session_id", table_name="attendance_events")
    op.drop_table("attendance_events")
    op.drop_index("ix_recognition_attempts_client_key", table_name="recognition_attempts")
    op.drop_index("ix_recognition_attempts_session_id", table_name="recognition_attempts")
    op.drop_table("recognition_attempts")
    op.drop_index("ix_face_embeddings_person_id", table_name="face_embeddings")
    op.drop_table("face_embeddings")
    op.drop_index("ix_enrollment_samples_batch_id", table_name="enrollment_samples")
    op.drop_table("enrollment_samples")
    op.drop_index("ix_session_allowed_persons_person_id", table_name="session_allowed_persons")
    op.drop_index("ix_session_allowed_persons_session_id", table_name="session_allowed_persons")
    op.drop_table("session_allowed_persons")
    op.drop_index("ix_enrollment_batches_person_id", table_name="enrollment_batches")
    op.drop_table("enrollment_batches")
    op.drop_table("attendance_sessions")
    op.drop_table("app_settings")
    op.drop_table("persons")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

