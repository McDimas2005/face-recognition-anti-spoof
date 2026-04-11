"""self enrollment support

Revision ID: 0002_self_enrollment_support
Revises: 0001_initial_schema
Create Date: 2026-04-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_self_enrollment_support"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("owner_user_id", sa.String(length=36), nullable=True))
    op.create_unique_constraint("uq_persons_owner_user_id", "persons", ["owner_user_id"])
    op.create_foreign_key("fk_persons_owner_user_id_users", "persons", "users", ["owner_user_id"], ["id"])

    op.add_column("enrollment_batches", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("enrollment_batches", sa.Column("is_self_enrollment", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        "enrollment_batches",
        sa.Column("bypass_quality_validation", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("enrollment_batches", sa.Column("target_sample_count", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("enrollment_batches", sa.Column("replacement_for_batch_id", sa.String(length=36), nullable=True))
    op.add_column("enrollment_batches", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_enrollment_batches_replacement_for_batch_id",
        "enrollment_batches",
        "enrollment_batches",
        ["replacement_for_batch_id"],
        ["id"],
    )

    op.add_column("enrollment_samples", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("enrollment_samples", sa.Column("capture_index", sa.Integer(), nullable=True))

    op.add_column("face_embeddings", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.execute("UPDATE enrollment_batches SET is_active = CASE WHEN status = 'ready' THEN true ELSE false END")
    op.execute("UPDATE enrollment_samples SET is_active = quality_passed")
    op.execute("UPDATE enrollment_batches SET target_sample_count = 5 WHERE target_sample_count IS NULL")
    op.execute("UPDATE face_embeddings SET is_active = true")

    op.alter_column("enrollment_batches", "is_active", server_default=None)
    op.alter_column("enrollment_batches", "is_self_enrollment", server_default=None)
    op.alter_column("enrollment_batches", "bypass_quality_validation", server_default=None)
    op.alter_column("enrollment_batches", "target_sample_count", server_default=None)
    op.alter_column("enrollment_samples", "is_active", server_default=None)
    op.alter_column("face_embeddings", "is_active", server_default=None)


def downgrade() -> None:
    op.alter_column("face_embeddings", "is_active", server_default=sa.true())
    op.drop_column("face_embeddings", "is_active")

    op.alter_column("enrollment_samples", "is_active", server_default=sa.false())
    op.drop_column("enrollment_samples", "capture_index")
    op.drop_column("enrollment_samples", "is_active")

    op.drop_constraint("fk_enrollment_batches_replacement_for_batch_id", "enrollment_batches", type_="foreignkey")
    op.drop_column("enrollment_batches", "finalized_at")
    op.drop_column("enrollment_batches", "replacement_for_batch_id")
    op.drop_column("enrollment_batches", "target_sample_count")
    op.drop_column("enrollment_batches", "bypass_quality_validation")
    op.drop_column("enrollment_batches", "is_self_enrollment")
    op.drop_column("enrollment_batches", "is_active")

    op.drop_constraint("fk_persons_owner_user_id_users", "persons", type_="foreignkey")
    op.drop_constraint("uq_persons_owner_user_id", "persons", type_="unique")
    op.drop_column("persons", "owner_user_id")
