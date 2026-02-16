from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("birth_month BETWEEN 1 AND 12", name="ck_users_birth_month_range"),
        CheckConstraint("birth_year >= 1900", name="ck_users_birth_year_min"),
        CheckConstraint(
            "birth_year <= EXTRACT(YEAR FROM CURRENT_DATE)::INT",
            name="ck_users_birth_year_max_current",
        ),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    birth_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
