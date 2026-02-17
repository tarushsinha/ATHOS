from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.models.cardio_session import CardioSession
from app.db.models.enums import Modality
from app.db.models.exercise import Exercise
from app.db.models.strength_set import StrengthSet
from app.db.models.workout import Workout
from app.db.session import get_db
from app.schemas.workouts import WorkoutCreateRequest, WorkoutCreateResponse

router = APIRouter(prefix="/v1/workouts", tags=["workouts"])

IDEMPOTENCY_CONSTRAINT = "uq_workouts_user_client_uuid_not_null"
EXERCISE_NAME_UNIQUE_CONSTRAINT = "uq_exercises_user_name_lower"


def _is_exercise_name_conflict(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name == EXERCISE_NAME_UNIQUE_CONSTRAINT:
        return True
    return EXERCISE_NAME_UNIQUE_CONSTRAINT in str(exc.orig)


def _get_or_create_exercise(
    db: Session,
    user_id: int,
    exercise_id: UUID | None,
    exercise_name: str | None,
) -> Exercise:
    if exercise_id is not None:
        exercise = db.execute(
            select(Exercise).where(
                Exercise.id == exercise_id,
                Exercise.user_id == user_id,
            )
        ).scalar_one_or_none()
        if exercise is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exercise not found",
            )
        return exercise

    assert exercise_name is not None
    normalized_name = exercise_name.strip()

    exercise = db.execute(
        select(Exercise).where(
            Exercise.user_id == user_id,
            func.lower(Exercise.name) == normalized_name.lower(),
        )
    ).scalar_one_or_none()

    if exercise is not None:
        return exercise

    # Concurrency-safe create-on-write:
    # use a SAVEPOINT so unique conflicts on exercise name don't abort
    # the outer workout transaction.
    try:
        with db.begin_nested():
            exercise = Exercise(
                user_id=user_id,
                name=normalized_name,
                default_modality=Modality.STRENGTH,
            )
            db.add(exercise)
            db.flush()
            return exercise
    except IntegrityError as exc:
        if not _is_exercise_name_conflict(exc):
            raise

    exercise = db.execute(
        select(Exercise).where(
            Exercise.user_id == user_id,
            func.lower(Exercise.name) == normalized_name.lower(),
        )
    ).scalar_one_or_none()
    if exercise is not None:
        return exercise
    raise


def _is_idempotency_conflict(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name == IDEMPOTENCY_CONSTRAINT:
        return True
    return IDEMPOTENCY_CONSTRAINT in str(exc.orig)


@router.post("", response_model=WorkoutCreateResponse, status_code=status.HTTP_201_CREATED)
def create_workout(
    payload: WorkoutCreateRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    workout = Workout(
        user_id=current_user_id,
        workout_type=payload.workout_type,
        title=payload.title,
        start_ts=payload.start_ts,
        end_ts=payload.end_ts,
        source=payload.source,
        provider=payload.provider,
        client_uuid=payload.client_uuid,
    )

    strength_count = 0
    cardio_created = False

    try:
        db.add(workout)
        db.flush()

        if payload.strength_sets:
            for idx, set_payload in enumerate(payload.strength_sets, start=1):
                exercise = _get_or_create_exercise(
                    db=db,
                    user_id=current_user_id,
                    exercise_id=set_payload.exercise_id,
                    exercise_name=set_payload.exercise_name,
                )

                db.add(
                    StrengthSet(
                        user_id=current_user_id,
                        workout_id=workout.id,
                        exercise_id=exercise.id,
                        set_index=set_payload.set_index or idx,
                        weight=set_payload.weight,
                        reps=set_payload.reps,
                        duration_seconds=set_payload.duration_seconds,
                        rpe=set_payload.rpe,
                        notes=set_payload.notes,
                    )
                )
                strength_count += 1

        elif payload.cardio_session is not None:
            db.add(
                CardioSession(
                    user_id=current_user_id,
                    workout_id=workout.id,
                    distance_miles=payload.cardio_session.distance_miles,
                    duration_seconds=payload.cardio_session.duration_seconds,
                    incline=payload.cardio_session.incline,
                    speed_mph=payload.cardio_session.speed_mph,
                    resistance=payload.cardio_session.resistance,
                    rpms=payload.cardio_session.rpms,
                    notes=payload.cardio_session.notes,
                )
            )
            cardio_created = True

        db.commit()

    except IntegrityError as exc:
        db.rollback()
        if payload.client_uuid is not None and _is_idempotency_conflict(exc):
            existing_workout = db.execute(
                select(Workout).where(
                    Workout.user_id == current_user_id,
                    Workout.client_uuid == payload.client_uuid,
                )
            ).scalar_one_or_none()
            if existing_workout is not None:
                resp = WorkoutCreateResponse(
                    workout_id=existing_workout.id,
                    workout_type=existing_workout.workout_type,
                    strength_set_count=0,
                    cardio_session_created=False,
                )
                return JSONResponse(
                    content=resp.model_dump(mode="json"),
                    status_code=status.HTTP_200_OK,
                )
        raise
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return WorkoutCreateResponse(
        workout_id=workout.id,
        workout_type=workout.workout_type,
        strength_set_count=strength_count,
        cardio_session_created=cardio_created,
    )
