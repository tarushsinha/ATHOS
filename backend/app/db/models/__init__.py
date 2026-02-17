"""SQLAlchemy model package.

Import model modules here as they are added so Alembic autogenerate
can discover them via metadata.
"""

from app.db.models.user import User  # noqa: F401
from app.db.models.cardio_session import CardioSession  # noqa: F401
from app.db.models.exercise import Exercise  # noqa: F401
from app.db.models.muscle_group import ExerciseMuscleMap, MuscleGroup  # noqa: F401
from app.db.models.strength_set import StrengthSet  # noqa: F401
from app.db.models.workout import Workout  # noqa: F401
