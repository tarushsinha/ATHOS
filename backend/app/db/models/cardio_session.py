from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CardioSession(Base):
    __tablename__ = "cardio_sessions"
    __table_args__ = (
        Index("cardio_sessions_user_time", "user_id", "workout_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    workout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    distance_miles: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incline: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    speed_mph: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    resistance: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    rpms: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
