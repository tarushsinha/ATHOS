from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.models.cardio_session import CardioSession
from app.db.models.enums import Modality
from app.db.models.exercise import Exercise
from app.db.models.muscle_group import ExerciseMuscleMap, MuscleGroup
from app.db.models.strength_set import StrengthSet
from app.db.models.workout import Workout
from app.db.session import get_db
from app.schemas.dashboard import (
    CardioSessionDetailResponse,
    CardioTotalsResponse,
    DashboardDayResponse,
    DayTelemetryResponse,
    MaxWeightPerExerciseResponse,
    MuscleGroupTrainingLoadResponse,
    StrengthSetDashboardResponse,
    WorkoutDashboardItemResponse,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


def _resolve_client_timezone(client_timezone: str | None) -> ZoneInfo:
    if not client_timezone:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(client_timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid X-Client-Timezone header",
        ) from None


@router.get("/day", response_model=DashboardDayResponse)
def dashboard_day(
    dashboard_date: date_cls = Query(..., alias="date"),
    limit: int = Query(50, ge=1, le=200),
    top_k: int = Query(10, ge=1, le=50),
    client_timezone: str | None = Header(default=None, alias="X-Client-Timezone"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    tz = _resolve_client_timezone(client_timezone)
    local_start = datetime.combine(dashboard_date, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)

    workouts = db.execute(
        select(Workout)
        .where(
            Workout.user_id == current_user_id,
            Workout.start_ts >= start_utc,
            Workout.start_ts < end_utc,
        )
        .order_by(Workout.start_ts.desc())
        .limit(limit)
    ).scalars().all()

    workout_ids = [w.id for w in workouts]
    if not workout_ids:
        return DashboardDayResponse(
            workouts=[],
            telemetry=DayTelemetryResponse(
                total_training_load=0.0,
                best_set_load=None,
                best_set_exercise_name=None,
                max_weight_per_exercise=[],
                muscle_group_training_load=[],
                cardio_totals=CardioTotalsResponse(
                    total_distance_miles=0.0,
                    total_duration_seconds=None,
                ),
            ),
        )

    strength_rows = db.execute(
        select(StrengthSet, Exercise.name.label("exercise_name"))
        .join(Exercise, Exercise.id == StrengthSet.exercise_id)
        .where(
            StrengthSet.user_id == current_user_id,
            StrengthSet.workout_id.in_(workout_ids),
            Exercise.user_id == current_user_id,
        )
        .order_by(
            StrengthSet.workout_id,
            StrengthSet.set_index.is_(None),
            StrengthSet.set_index.asc(),
            StrengthSet.id.asc(),
        )
    ).all()

    cardio_rows = db.execute(
        select(CardioSession)
        .where(
            CardioSession.user_id == current_user_id,
            CardioSession.workout_id.in_(workout_ids),
        )
    ).scalars().all()

    exercise_ids = list({set_row.exercise_id for set_row, _ in strength_rows})
    exercise_group_names: dict[UUID, list[str]] = defaultdict(list)
    exercise_primary_group_names: dict[UUID, list[str]] = defaultdict(list)

    if exercise_ids:
        mappings = db.execute(
            select(
                ExerciseMuscleMap.exercise_id,
                ExerciseMuscleMap.is_primary,
                MuscleGroup.name,
            )
            .join(MuscleGroup, MuscleGroup.id == ExerciseMuscleMap.muscle_group_id)
            .where(ExerciseMuscleMap.exercise_id.in_(exercise_ids))
        ).all()

        for exercise_id, is_primary, muscle_group_name in mappings:
            exercise_group_names[exercise_id].append(muscle_group_name)
            if is_primary:
                exercise_primary_group_names[exercise_id].append(muscle_group_name)

    strength_by_workout: dict[UUID, list[StrengthSetDashboardResponse]] = defaultdict(list)
    cardio_by_workout: dict[UUID, CardioSessionDetailResponse] = {}

    total_training_load = 0.0
    best_set_load: float | None = None
    best_set_exercise_name: str | None = None
    max_weight_by_exercise: dict[str, float] = {}
    muscle_group_loads: dict[str, float] = defaultdict(float)

    for set_row, exercise_name in strength_rows:
        selected_groups = exercise_primary_group_names.get(set_row.exercise_id) or exercise_group_names.get(
            set_row.exercise_id, []
        )

        strength_by_workout[set_row.workout_id].append(
            StrengthSetDashboardResponse(
                id=set_row.id,
                workout_id=set_row.workout_id,
                exercise_id=set_row.exercise_id,
                exercise_name=exercise_name,
                set_index=set_row.set_index,
                weight=set_row.weight,
                reps=set_row.reps,
                duration_seconds=set_row.duration_seconds,
                rpe=set_row.rpe,
                notes=set_row.notes,
                muscle_groups=selected_groups,
            )
        )

        if set_row.weight is not None:
            weight_value = float(set_row.weight)
            current_max = max_weight_by_exercise.get(exercise_name)
            if current_max is None or weight_value > current_max:
                max_weight_by_exercise[exercise_name] = weight_value

        if set_row.weight is not None and set_row.reps is not None:
            load = float(set_row.weight) * float(set_row.reps)
            total_training_load += load

            if best_set_load is None or load > best_set_load:
                best_set_load = load
                best_set_exercise_name = exercise_name

            for muscle_group_name in selected_groups:
                muscle_group_loads[muscle_group_name] += load

    total_distance_miles = 0.0
    total_duration_seconds_value = 0
    has_duration = False

    for cardio in cardio_rows:
        cardio_by_workout[cardio.workout_id] = CardioSessionDetailResponse(
            id=cardio.id,
            workout_id=cardio.workout_id,
            distance_miles=cardio.distance_miles,
            duration_seconds=cardio.duration_seconds,
            incline=cardio.incline,
            speed_mph=cardio.speed_mph,
            resistance=cardio.resistance,
            rpms=cardio.rpms,
            notes=cardio.notes,
        )

        if cardio.distance_miles is not None:
            total_distance_miles += float(cardio.distance_miles)
        if cardio.duration_seconds is not None:
            total_duration_seconds_value += int(cardio.duration_seconds)
            has_duration = True

    workout_items: list[WorkoutDashboardItemResponse] = []
    for workout in workouts:
        workout_items.append(
            WorkoutDashboardItemResponse(
                id=workout.id,
                workout_type=workout.workout_type,
                title=workout.title,
                start_ts=workout.start_ts,
                end_ts=workout.end_ts,
                source=workout.source,
                provider=workout.provider,
                client_uuid=workout.client_uuid,
                strength_sets=strength_by_workout.get(workout.id, []) if workout.workout_type == Modality.STRENGTH else [],
                cardio_session=cardio_by_workout.get(workout.id) if workout.workout_type == Modality.CARDIO else None,
            )
        )

    max_weight_per_exercise = sorted(
        [
            MaxWeightPerExerciseResponse(exercise_name=name, max_weight=max_weight)
            for name, max_weight in max_weight_by_exercise.items()
        ],
        key=lambda x: x.max_weight,
        reverse=True,
    )[:top_k]

    muscle_group_training_load = sorted(
        [
            MuscleGroupTrainingLoadResponse(muscle_group=name, load=load)
            for name, load in muscle_group_loads.items()
        ],
        key=lambda x: x.load,
        reverse=True,
    )

    telemetry = DayTelemetryResponse(
        total_training_load=total_training_load,
        best_set_load=best_set_load,
        best_set_exercise_name=best_set_exercise_name,
        max_weight_per_exercise=max_weight_per_exercise,
        muscle_group_training_load=muscle_group_training_load,
        cardio_totals=CardioTotalsResponse(
            total_distance_miles=total_distance_miles,
            total_duration_seconds=total_duration_seconds_value if has_duration else None,
        ),
    )

    return DashboardDayResponse(workouts=workout_items, telemetry=telemetry)
