"""Add Case projection pointer foreign keys.

Revision ID: 0002_case_projection_pointer_fks
Revises: 0001_closed_loop_schema
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_case_projection_pointer_fks"
down_revision: Union[str, Sequence[str], None] = "0001_closed_loop_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ANALYSIS_FOREIGN_KEY = "fk_case_projection_current_analysis_id_analysis_versions"
_DECISION_FOREIGN_KEY = "fk_case_projection_current_decision_id_decisions"


def upgrade() -> None:
    """Add nullable, restrictive projection-pointer constraints."""
    with op.batch_alter_table("case_projection", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            _ANALYSIS_FOREIGN_KEY,
            "analysis_versions",
            ["current_analysis_id"],
            ["analysis_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            _DECISION_FOREIGN_KEY,
            "decisions",
            ["current_decision_id"],
            ["decision_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """Remove projection-pointer constraints while preserving revision 0001."""
    with op.batch_alter_table("case_projection", recreate="always") as batch_op:
        batch_op.drop_constraint(_DECISION_FOREIGN_KEY, type_="foreignkey")
        batch_op.drop_constraint(_ANALYSIS_FOREIGN_KEY, type_="foreignkey")
