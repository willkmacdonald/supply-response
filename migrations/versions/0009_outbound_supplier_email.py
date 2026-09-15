"""Add versioned reviewed supplier email state.

Revision ID: 0009_outbound_supplier_email
Revises: 0008_case_proposal_selection
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_outbound_supplier_email"
down_revision: str | Sequence[str] | None = "0008_case_proposal_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "supplier_email_deliveries" not in existing:
        op.create_table(
            "supplier_email_deliveries",
            sa.Column("email_id", sa.String(128), nullable=False),
            sa.Column("decision_id", sa.String(128), nullable=False),
            sa.Column("reviewed_revision", sa.Integer(), nullable=True),
            sa.Column("send_status", sa.String(32), nullable=False),
            sa.Column("provider_message_id", sa.String(256), nullable=True),
            sa.Column("internet_message_id", sa.String(512), nullable=True),
            sa.Column("correlation_id", sa.String(128), nullable=True),
            sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("failure_code", sa.String(128), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("email_id", name="pk_supplier_email_deliveries"),
            sa.UniqueConstraint(
                "decision_id", name="uq_supplier_email_deliveries_decision_id"
            ),
            sa.CheckConstraint(
                "reviewed_revision IS NULL OR reviewed_revision > 0",
                name=op.f("ck_supplier_email_deliveries_reviewed_revision_positive"),
            ),
            sa.CheckConstraint(
                "send_status IN ('draft', 'submitting', 'accepted', 'sent-confirmed', 'failed', 'uncertain')",
                name=op.f("ck_supplier_email_deliveries_send_status_valid"),
            ),
            sa.ForeignKeyConstraint(
                ["decision_id"],
                ["decisions.decision_id"],
                ondelete="RESTRICT",
                name="fk_supplier_email_deliveries_decision_id_decisions",
            ),
        )
        op.create_index(
            "ix_supplier_email_deliveries_decision_id",
            "supplier_email_deliveries",
            ["decision_id"],
        )
        op.create_index(
            "ix_supplier_email_deliveries_send_status",
            "supplier_email_deliveries",
            ["send_status"],
        )
        op.create_index(
            "ix_supplier_email_deliveries_status_updated_at",
            "supplier_email_deliveries",
            ["status_updated_at"],
        )
    if "supplier_email_revisions" not in existing:
        op.create_table(
            "supplier_email_revisions",
            sa.Column("email_id", sa.String(128), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("decision_id", sa.String(128), nullable=False),
            sa.Column("action_id", sa.String(128), nullable=False),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("from_address", sa.String(320), nullable=False),
            sa.Column("to_address", sa.String(320), nullable=False),
            sa.Column("edited_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint(
                "email_id", "revision", name="pk_supplier_email_revisions"
            ),
            sa.UniqueConstraint(
                "email_id",
                "revision",
                name="uq_supplier_email_revisions_email_revision",
            ),
            sa.CheckConstraint(
                "revision > 0",
                name=op.f("ck_supplier_email_revisions_revision_positive"),
            ),
            sa.ForeignKeyConstraint(
                ["decision_id"],
                ["decisions.decision_id"],
                ondelete="RESTRICT",
                name="fk_supplier_email_revisions_decision_id_decisions",
            ),
            sa.ForeignKeyConstraint(
                ["action_id"],
                ["execution_actions.action_id"],
                ondelete="RESTRICT",
                name="fk_supplier_email_revisions_action_id_execution_actions",
            ),
        )
        for column in ("decision_id", "action_id", "edited_at", "reviewed_at"):
            op.create_index(
                f"ix_supplier_email_revisions_{column}",
                "supplier_email_revisions",
                [column],
            )


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "supplier_email_revisions" in existing:
        op.drop_table("supplier_email_revisions")
    if "supplier_email_deliveries" in existing:
        op.drop_table("supplier_email_deliveries")
