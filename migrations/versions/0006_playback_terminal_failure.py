"""Add durable playback terminal failure state.

Revision ID: 0006_playback_terminal_failure
Revises: 0005_analysis_claims
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_playback_terminal_failure"
down_revision: str | Sequence[str] | None = "0005_analysis_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns("playbacks")
    }
    if "failed_at" not in columns:
        op.add_column(
            "playbacks",
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "error_code" not in columns:
        op.add_column(
            "playbacks", sa.Column("error_code", sa.String(length=64), nullable=True)
        )


def downgrade() -> None:
    columns = {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns("playbacks")
    }
    if "error_code" in columns:
        op.drop_column("playbacks", "error_code")
    if "failed_at" in columns:
        op.drop_column("playbacks", "failed_at")
