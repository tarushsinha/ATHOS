"""create core workout domain tables

Revision ID: 541b7f5ef07c
Revises: fc59ff8f8b98
Create Date: 2026-02-16 22:01:49.385938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql



# revision identifiers, used by Alembic.
revision: str = '541b7f5ef07c'
down_revision: Union[str, Sequence[str], None] = 'fc59ff8f8b98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    modality_enum_for_create = postgresql.ENUM("STRENGTH", "CARDIO", "OTHER", name="modality")
    modality_enum_for_create.create(bind, checkfirst=True)
    modality_enum = postgresql.ENUM(
        "STRENGTH",
        "CARDIO",
        "OTHER",
        name="modality",
        create_type=False,
    )

    op.create_table(
        "muscle_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_modality", modality_enum, server_default=sa.text("'OTHER'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exercises_user_id"), "exercises", ["user_id"], unique=False)
    op.create_index(
        "uq_exercises_user_name_lower",
        "exercises",
        ["user_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "workouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workout_type", modality_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("client_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workouts_user_id"), "workouts", ["user_id"], unique=False)
    op.create_index(
        "uq_workouts_user_client_uuid_not_null",
        "workouts",
        ["user_id", "client_uuid"],
        unique=True,
        postgresql_where=sa.text("client_uuid IS NOT NULL"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS workouts_user_time ON workouts (user_id, start_ts DESC)"
    )

    op.create_table(
        "cardio_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("distance_miles", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("incline", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("speed_mph", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("resistance", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("rpms", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["workout_id"], ["workouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workout_id"),
    )
    op.create_index("cardio_sessions_user_time", "cardio_sessions", ["user_id", "workout_id"], unique=False)
    op.create_index(op.f("ix_cardio_sessions_user_id"), "cardio_sessions", ["user_id"], unique=False)

    op.create_table(
        "exercise_muscle_map",
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("muscle_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["muscle_group_id"], ["muscle_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exercise_id", "muscle_group_id"),
    )

    op.create_table(
        "strength_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("set_index", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("rpe", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["workout_id"], ["workouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strength_sets_user_id"), "strength_sets", ["user_id"], unique=False)
    op.create_index("strength_sets_workout_order", "strength_sets", ["workout_id", "set_index"], unique=False)


def downgrade() -> None:
    op.drop_index('strength_sets_workout_order', table_name='strength_sets')
    op.drop_index(op.f('ix_strength_sets_user_id'), table_name='strength_sets')
    op.drop_table('strength_sets')
    op.drop_table('exercise_muscle_map')
    op.drop_index(op.f('ix_cardio_sessions_user_id'), table_name='cardio_sessions')
    op.drop_index('cardio_sessions_user_time', table_name='cardio_sessions')
    op.drop_table('cardio_sessions')
    op.execute("DROP INDEX IF EXISTS workouts_user_time")
    op.drop_index('uq_workouts_user_client_uuid_not_null', table_name='workouts', postgresql_where=sa.text('client_uuid IS NOT NULL'))
    op.drop_index(op.f('ix_workouts_user_id'), table_name='workouts')
    op.drop_table('workouts')
    op.drop_index('uq_exercises_user_name_lower', table_name='exercises')
    op.drop_index(op.f('ix_exercises_user_id'), table_name='exercises')
    op.drop_table('exercises')
    op.drop_table('muscle_groups')
    bind = op.get_bind()
    modality_enum = postgresql.ENUM("STRENGTH", "CARDIO", "OTHER", name="modality")
    modality_enum.drop(bind, checkfirst=True)
