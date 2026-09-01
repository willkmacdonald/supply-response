"""Add cross-process analysis material claims.

Revision ID: 0005_analysis_claims
Revises: 0004_simulated_playback_observations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_analysis_claims"
down_revision: str | Sequence[str] | None = "0004_simulated_playback_observations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("analysis_claims"):
        return
    op.create_table(
        "analysis_claims",
        sa.Column("case_id", sa.String(128), nullable=False),
        sa.Column("material_version", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_instances.case_id"],
            name=op.f("fk_analysis_claims_case_id_case_instances"),
        ),
        sa.PrimaryKeyConstraint(
            "case_id", "material_version", name=op.f("pk_analysis_claims")
        ),
        sa.UniqueConstraint("claim_id", name=op.f("uq_analysis_claims_claim_id")),
    )
    op.create_index(
        op.f("ix_analysis_claims_claimed_at"), "analysis_claims", ["claimed_at"]
    )
    op.create_index(
        op.f("ix_analysis_claims_claim_expires_at"),
        "analysis_claims",
        ["claim_expires_at"],
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("analysis_claims"):
        return
    op.drop_index(
        op.f("ix_analysis_claims_claim_expires_at"), table_name="analysis_claims"
    )
    op.drop_index(op.f("ix_analysis_claims_claimed_at"), table_name="analysis_claims")
    op.drop_table("analysis_claims")
