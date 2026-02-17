from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.db.models.enums import Modality


class StrengthSetInput(BaseModel):
    exercise_id: UUID | None = None
    exercise_name: str | None = Field(default=None, min_length=1, max_length=255)
    set_index: int | None = Field(default=None, ge=1)
    weight: float | None = None
    reps: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    rpe: float | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_exercise_ref(self) -> "StrengthSetInput":
        if self.exercise_id is None and not self.exercise_name:
            raise ValueError("Provide exercise_id or exercise_name")
        return self


class CardioSessionInput(BaseModel):
    distance_miles: float | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    incline: float | None = None
    speed_mph: float | None = None
    resistance: float | None = None
    rpms: float | None = None
    notes: str | None = None


class WorkoutCreateRequest(BaseModel):
    workout_type: Modality
    title: str | None = Field(default=None, max_length=255)
    start_ts: datetime
    end_ts: datetime | None = None
    source: str | None = Field(default=None, max_length=50)
    provider: str | None = Field(default=None, max_length=100)
    client_uuid: UUID | None = None
    strength_sets: list[StrengthSetInput] | None = None
    cardio_session: CardioSessionInput | None = None

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "WorkoutCreateRequest":
        has_strength = bool(self.strength_sets)
        has_cardio = self.cardio_session is not None

        if has_strength == has_cardio:
            raise ValueError("Provide exactly one of strength_sets or cardio_session")

        if has_strength and self.workout_type != Modality.STRENGTH:
            raise ValueError("workout_type must be STRENGTH when strength_sets are provided")

        if has_cardio and self.workout_type != Modality.CARDIO:
            raise ValueError("workout_type must be CARDIO when cardio_session is provided")

        return self


class WorkoutCreateResponse(BaseModel):
    workout_id: UUID
    workout_type: Modality
    strength_set_count: int = 0
    cardio_session_created: bool = False
