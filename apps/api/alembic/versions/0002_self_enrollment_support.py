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
    with op.batch_alter_table("persons") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        batch_op.create_unique_constraint("uq_persons_owner_user_id", ["owner_user_id"])
        batch_op.create_foreign_key("fk_persons_owner_user_id_users", "users", ["owner_user_id"], ["id"])

    with op.batch_alter_table("enrollment_batches") as batch_op:
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("is_self_enrollment", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(
            sa.Column("bypass_quality_validation", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        batch_op.add_column(sa.Column("target_sample_count", sa.Integer(), nullable=False, server_default="5"))
        batch_op.add_column(sa.Column("replacement_for_batch_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_enrollment_batches_replacement_for_batch_id",
            "enrollment_batches",
            ["replacement_for_batch_id"],
            ["id"],
        )

    with op.batch_alter_table("enrollment_samples") as batch_op:
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("capture_index", sa.Integer(), nullable=True))

    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.execute("UPDATE enrollment_batches SET is_active = CASE WHEN status = 'ready' THEN true ELSE false END")
    op.execute("UPDATE enrollment_samples SET is_active = quality_passed")
    op.execute("UPDATE enrollment_batches SET target_sample_count = 5 WHERE target_sample_count IS NULL")
    op.execute("UPDATE face_embeddings SET is_active = true")

    with op.batch_alter_table("enrollment_batches") as batch_op:
        batch_op.alter_column("is_active", server_default=None)
        batch_op.alter_column("is_self_enrollment", server_default=None)
        batch_op.alter_column("bypass_quality_validation", server_default=None)
        batch_op.alter_column("target_sample_count", server_default=None)
    with op.batch_alter_table("enrollment_samples") as batch_op:
        batch_op.alter_column("is_active", server_default=None)
    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.alter_column("is_active", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.alter_column("is_active", server_default=sa.true())
        batch_op.drop_column("is_active")

    with op.batch_alter_table("enrollment_samples") as batch_op:
        batch_op.alter_column("is_active", server_default=sa.false())
        batch_op.drop_column("capture_index")
        batch_op.drop_column("is_active")

    with op.batch_alter_table("enrollment_batches") as batch_op:
        batch_op.drop_constraint("fk_enrollment_batches_replacement_for_batch_id", type_="foreignkey")
        batch_op.drop_column("finalized_at")
        batch_op.drop_column("replacement_for_batch_id")
        batch_op.drop_column("target_sample_count")
        batch_op.drop_column("bypass_quality_validation")
        batch_op.drop_column("is_self_enrollment")
        batch_op.drop_column("is_active")

    with op.batch_alter_table("persons") as batch_op:
        batch_op.drop_constraint("fk_persons_owner_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("uq_persons_owner_user_id", type_="unique")
        batch_op.drop_column("owner_user_id")
