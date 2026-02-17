from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.enums import Modality
from app.db.session import Base


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        Index(
            "uq_exercises_user_name_lower",
            "user_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_modality: Mapped[Modality] = mapped_column(
        Enum(Modality, name="modality"),
        nullable=False,
        server_default=Modality.OTHER.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
