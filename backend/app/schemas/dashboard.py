from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import Modality
from app.schemas.workouts import CardioSessionDetailResponse


class StrengthSetDashboardResponse(BaseModel):
    id: UUID
    workout_id: UUID
    exercise_id: UUID
    exercise_name: str
    set_index: int
    weight: float | None
    reps: int | None
    duration_seconds: int | None
    rpe: float | None
    notes: str | None
    muscle_groups: list[str] = Field(default_factory=list)


class WorkoutDashboardItemResponse(BaseModel):
    id: UUID
    workout_type: Modality
    title: str | None
    start_ts: datetime
    end_ts: datetime | None
    source: str | None
    provider: str | None
    client_uuid: UUID | None
    strength_sets: list[StrengthSetDashboardResponse] = Field(default_factory=list)
    cardio_session: CardioSessionDetailResponse | None = None


class MaxWeightPerExerciseResponse(BaseModel):
    exercise_name: str
    max_weight: float


class MuscleGroupTrainingLoadResponse(BaseModel):
    muscle_group: str
    load: float


class CardioTotalsResponse(BaseModel):
    total_distance_miles: float
    total_duration_seconds: int | None


class DayTelemetryResponse(BaseModel):
    total_training_load: float
    best_set_load: float | None
    best_set_exercise_name: str | None
    max_weight_per_exercise: list[MaxWeightPerExerciseResponse] = Field(default_factory=list)
    muscle_group_training_load: list[MuscleGroupTrainingLoadResponse] = Field(default_factory=list)
    cardio_totals: CardioTotalsResponse


class DashboardDayResponse(BaseModel):
    workouts: list[WorkoutDashboardItemResponse] = Field(default_factory=list)
    telemetry: DayTelemetryResponse
