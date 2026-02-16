"""SQLAlchemy model package.

Import model modules here as they are added so Alembic autogenerate
can discover them via metadata.
"""

from app.db.models.user import User  # noqa: F401
