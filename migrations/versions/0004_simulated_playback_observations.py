"""Enforce deterministic simulated playback and observation provenance.

Revision ID: 0004_simulated_playback_observations
Revises: 0003_outbox_one_planning_event
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_simulated_playback_observations"
down_revision: Union[str, Sequence[str], None] = "0003_outbox_one_planning_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PLAYBACK_UNIQUE = "uq_playback_per_decision"
_PROVENANCE_CHECK = "observation_kind_synthetic_provenance"


def upgrade() -> None:
    """Add Task 8 linkage fields and permanent simulated provenance guards."""
    with op.batch_alter_table("playbacks", recreate="always") as batch_op:
        batch_op.create_unique_constraint(_PLAYBACK_UNIQUE, ["decision_id"])

    with op.batch_alter_table("outcome_observations", recreate="always") as batch_op:
        batch_op.alter_column("observation_kind", new_column_name="kind")
        batch_op.alter_column("observed_at", new_column_name="recorded_at")
        batch_op.add_column(sa.Column("action_id", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("metric", sa.String(128), nullable=False))
        batch_op.add_column(sa.Column("observed_value", sa.String(128), nullable=False))
        batch_op.add_column(sa.Column("unit", sa.String(32), nullable=False))
        batch_op.add_column(
            sa.Column("predicted_value", sa.String(128), nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "scenario_effective_time",
                sa.DateTime(timezone=True),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("scenario_timezone", sa.String(64), nullable=False)
        )
        batch_op.add_column(
            sa.Column("source_reference", sa.String(256), nullable=False)
        )
        batch_op.add_column(sa.Column("synthetic", sa.Boolean(), nullable=False))
        batch_op.create_foreign_key(
            op.f("fk_outcome_observations_action_id_execution_actions"),
            "execution_actions",
            ["action_id"],
            ["action_id"],
        )
        batch_op.create_check_constraint(
            _PROVENANCE_CHECK,
            "(kind = 'simulated' AND synthetic = 1) OR "
            "(kind = 'actual' AND synthetic = 0)",
        )

    op.create_index(
        op.f("ix_outcome_observations_action_id"),
        "outcome_observations",
        ["action_id"],
    )
    op.create_index(
        op.f("ix_outcome_observations_metric"),
        "outcome_observations",
        ["metric"],
    )
    op.create_index(
        op.f("ix_outcome_observations_scenario_effective_time"),
        "outcome_observations",
        ["scenario_effective_time"],
    )
    op.create_index(
        op.f("ix_outcome_observations_synthetic"),
        "outcome_observations",
        ["synthetic"],
    )


def downgrade() -> None:
    """Remove Task 8 fields while retaining the original frozen schema."""
    op.drop_index(
        op.f("ix_outcome_observations_synthetic"),
        table_name="outcome_observations",
    )
    op.drop_index(
        op.f("ix_outcome_observations_scenario_effective_time"),
        table_name="outcome_observations",
    )
    op.drop_index(
        op.f("ix_outcome_observations_metric"),
        table_name="outcome_observations",
    )
    op.drop_index(
        op.f("ix_outcome_observations_action_id"),
        table_name="outcome_observations",
    )
    with op.batch_alter_table("outcome_observations", recreate="always") as batch_op:
        batch_op.drop_constraint(_PROVENANCE_CHECK, type_="check")
        batch_op.drop_constraint(
            op.f("fk_outcome_observations_action_id_execution_actions"),
            type_="foreignkey",
        )
        batch_op.drop_column("synthetic")
        batch_op.drop_column("source_reference")
        batch_op.drop_column("scenario_timezone")
        batch_op.drop_column("scenario_effective_time")
        batch_op.drop_column("predicted_value")
        batch_op.drop_column("unit")
        batch_op.drop_column("observed_value")
        batch_op.drop_column("metric")
        batch_op.drop_column("action_id")
        batch_op.alter_column("recorded_at", new_column_name="observed_at")
        batch_op.alter_column("kind", new_column_name="observation_kind")

    with op.batch_alter_table("playbacks", recreate="always") as batch_op:
        batch_op.drop_constraint(_PLAYBACK_UNIQUE, type_="unique")
