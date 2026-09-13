"""Add immutable Finance review revisions.

Revision ID: 0007_finance_review_revisions
Revises: 0006_playback_terminal_failure
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_finance_review_revisions"
down_revision: str | Sequence[str] | None = "0006_playback_terminal_failure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "finance_review_revisions" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "finance_review_revisions",
        sa.Column("review_id", sa.String(128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(128), nullable=False),
        sa.Column("analysis_id", sa.String(128), nullable=False),
        sa.Column("analysis_material_hash", sa.String(64), nullable=False),
        sa.Column("option_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint(
            "review_id", "revision", name="pk_finance_review_revisions"
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_finance_review_revisions_idempotency_key"
        ),
        sa.CheckConstraint(
            "revision > 0",
            name=op.f("ck_finance_review_revisions_revision_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_instances.case_id"],
            name="fk_finance_review_revisions_case_id_case_instances",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analysis_versions.analysis_id"],
            name="fk_finance_review_revisions_analysis_id_analysis_versions",
            ondelete="RESTRICT",
        ),
    )
    for column in (
        "case_id",
        "analysis_id",
        "analysis_material_hash",
        "option_id",
        "status",
        "recorded_at",
    ):
        op.create_index(
            f"ix_finance_review_revisions_{column}",
            "finance_review_revisions",
            [column],
        )


def downgrade() -> None:
    if "finance_review_revisions" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("finance_review_revisions")
