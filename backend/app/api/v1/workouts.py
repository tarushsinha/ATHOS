from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
import logging
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
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
from app.schemas.workouts import (
    CardioSessionDetailResponse,
    StrengthSetDetailResponse,
    WorkoutCreateRequest,
    WorkoutCreateResponse,
    WorkoutDetailResponse,
    WorkoutListItemResponse,
)

router = APIRouter(prefix="/v1/workouts", tags=["workouts"])
logger = logging.getLogger("athos.domain")

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


@router.post("", response_model=WorkoutCreateResponse, status_code=status.HTTP_201_CREATED)
def create_workout(
    payload: WorkoutCreateRequest,
    request: Request,
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
                logger.info(
                    "domain_event event=workout_idempotency_hit user_id=%s workout_id=%s request_id=%s",
                    current_user_id,
                    existing_workout.id,
                    getattr(request.state, "request_id", None),
                )
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

    logger.info(
        "domain_event event=workout_created user_id=%s workout_id=%s workout_type=%s strength_set_count=%s cardio_session_created=%s start_ts_defaulted=%s request_id=%s",
        current_user_id,
        workout.id,
        workout.workout_type.value,
        strength_count,
        cardio_created,
        payload.start_ts_defaulted,
        getattr(request.state, "request_id", None),
    )
    return WorkoutCreateResponse(
        workout_id=workout.id,
        workout_type=workout.workout_type,
        strength_set_count=strength_count,
        cardio_session_created=cardio_created,
    )


@router.get("", response_model=list[WorkoutListItemResponse])
def list_workouts(
    workout_date: date_cls = Query(..., alias="date"),
    limit: int = Query(20, ge=1, le=200),
    client_timezone: str | None = Header(default=None, alias="X-Client-Timezone"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    tz = _resolve_client_timezone(client_timezone)
    local_start = datetime.combine(workout_date, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)

    strength_counts = (
        select(
            StrengthSet.workout_id.label("workout_id"),
            func.count(StrengthSet.id).label("strength_set_count"),
        )
        .where(StrengthSet.user_id == current_user_id)
        .group_by(StrengthSet.workout_id)
        .subquery()
    )

    cardio_counts = (
        select(
            CardioSession.workout_id.label("workout_id"),
            func.count(CardioSession.id).label("cardio_count"),
        )
        .where(CardioSession.user_id == current_user_id)
        .group_by(CardioSession.workout_id)
        .subquery()
    )

    stmt = (
        select(
            Workout,
            func.coalesce(strength_counts.c.strength_set_count, 0).label("strength_set_count"),
            (func.coalesce(cardio_counts.c.cardio_count, 0) > 0).label("cardio_session_created"),
        )
        .outerjoin(strength_counts, strength_counts.c.workout_id == Workout.id)
        .outerjoin(cardio_counts, cardio_counts.c.workout_id == Workout.id)
        .where(
            Workout.user_id == current_user_id,
            Workout.start_ts >= start_utc,
            Workout.start_ts < end_utc,
        )
        .order_by(Workout.start_ts.desc())
        .limit(limit)
    )

    rows = db.execute(stmt).all()
    return [
        WorkoutListItemResponse(
            id=workout.id,
            workout_type=workout.workout_type,
            title=workout.title,
            start_ts=workout.start_ts,
            end_ts=workout.end_ts,
            source=workout.source,
            provider=workout.provider,
            client_uuid=workout.client_uuid,
            strength_set_count=int(strength_set_count),
            cardio_session_created=bool(cardio_session_created),
        )
        for workout, strength_set_count, cardio_session_created in rows
    ]


@router.get("/{workout_id}", response_model=WorkoutDetailResponse)
def get_workout(
    workout_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    workout = db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == current_user_id,
        )
    ).scalar_one_or_none()
    if workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    strength_sets: list[StrengthSetDetailResponse] = []
    cardio_session: CardioSessionDetailResponse | None = None

    if workout.workout_type == Modality.STRENGTH:
        strength_rows = db.execute(
            select(StrengthSet, Exercise.name.label("exercise_name"))
            .join(Exercise, Exercise.id == StrengthSet.exercise_id)
            .where(
                StrengthSet.workout_id == workout.id,
                StrengthSet.user_id == current_user_id,
            )
            .order_by(
                StrengthSet.set_index.is_(None),
                StrengthSet.set_index.asc(),
                StrengthSet.id.asc(),
            )
        ).all()
        strength_sets = [
            StrengthSetDetailResponse(
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
            )
            for set_row, exercise_name in strength_rows
        ]
    elif workout.workout_type == Modality.CARDIO:
        cardio = db.execute(
            select(CardioSession).where(
                CardioSession.workout_id == workout.id,
                CardioSession.user_id == current_user_id,
            )
        ).scalar_one_or_none()
        if cardio is not None:
            cardio_session = CardioSessionDetailResponse(
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

    return WorkoutDetailResponse(
        id=workout.id,
        workout_type=workout.workout_type,
        title=workout.title,
        start_ts=workout.start_ts,
        end_ts=workout.end_ts,
        source=workout.source,
        provider=workout.provider,
        client_uuid=workout.client_uuid,
        strength_sets=strength_sets,
        cardio_session=cardio_session,
    )
