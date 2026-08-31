"""Enforce one planning request event per approved Decision.

Revision ID: 0003_outbox_one_planning_event
Revises: 0002_case_projection_pointer_fks
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_outbox_one_planning_event"
down_revision: Union[str, Sequence[str], None] = "0002_case_projection_pointer_fks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OUTBOX_UNIQUE = "uq_outbox_event_per_decision"


def upgrade() -> None:
    """Prevent duplicate ActionPlanningRequested events for a Decision."""
    with op.batch_alter_table("outbox_events", recreate="always") as batch_op:
        batch_op.create_unique_constraint(
            _OUTBOX_UNIQUE,
            ["decision_id", "event_type"],
        )


def downgrade() -> None:
    """Remove the per-Decision outbox event uniqueness guard."""
    with op.batch_alter_table("outbox_events", recreate="always") as batch_op:
        batch_op.drop_constraint(_OUTBOX_UNIQUE, type_="unique")
