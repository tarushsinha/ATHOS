"""add birth month/year to users

Revision ID: fc59ff8f8b98
Revises: 393915da17c4
Create Date: 2026-02-16 06:53:27.453854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'fc59ff8f8b98'
down_revision: Union[str, Sequence[str], None] = '393915da17c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing dev databases may already contain users rows.
    # Strategy:
    # 1) Add columns nullable with temporary server defaults.
    # 2) Backfill any existing NULLs.
    # 3) Enforce NOT NULL + check constraints.
    # 4) Drop temporary defaults.
    op.add_column(
        "users",
        sa.Column("birth_year", sa.SmallInteger(), nullable=True, server_default=sa.text("1900")),
    )
    op.add_column(
        "users",
        sa.Column("birth_month", sa.SmallInteger(), nullable=True, server_default=sa.text("1")),
    )

    op.execute("UPDATE users SET birth_year = 1900 WHERE birth_year IS NULL")
    op.execute("UPDATE users SET birth_month = 1 WHERE birth_month IS NULL")

    op.alter_column("users", "birth_year", nullable=False)
    op.alter_column("users", "birth_month", nullable=False)

    op.create_check_constraint(
        "ck_users_birth_month_range",
        "users",
        "birth_month BETWEEN 1 AND 12",
    )
    op.create_check_constraint(
        "ck_users_birth_year_min",
        "users",
        "birth_year >= 1900",
    )
    op.create_check_constraint(
        "ck_users_birth_year_max_current",
        "users",
        "birth_year <= EXTRACT(YEAR FROM CURRENT_DATE)::INT",
    )

    op.alter_column("users", "birth_year", server_default=None)
    op.alter_column("users", "birth_month", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_users_birth_year_max_current", "users", type_="check")
    op.drop_constraint("ck_users_birth_year_min", "users", type_="check")
    op.drop_constraint("ck_users_birth_month_range", "users", type_="check")
    op.drop_column("users", "birth_month")
    op.drop_column("users", "birth_year")
