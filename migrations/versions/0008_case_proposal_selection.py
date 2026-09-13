"""Add immutable proposal selections and case generation."""

import sqlalchemy as sa
from alembic import op

revision = "0008_case_proposal_selection"
down_revision = "0007_finance_review_revisions"
branch_labels = None
depends_on = None
JOURNAL = "case_proposal_selections"
PAIR = "(finance_review_id IS NULL AND finance_review_revision IS NULL) OR (finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL AND finance_review_revision = 1)"
PROJECTION_FK = "fk_case_projection_current_selection_id_case_proposal_selections"
PROJECTION_CHECK = "ck_case_projection_proposal_generation_nonnegative"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if JOURNAL not in inspector.get_table_names():
        op.create_table(
            JOURNAL,
            sa.Column("selection_id", sa.String(128), nullable=False),
            sa.Column("case_id", sa.String(128), nullable=False),
            sa.Column("analysis_id", sa.String(128), nullable=False),
            sa.Column("analysis_material_hash", sa.String(64), nullable=False),
            sa.Column("workflow_version", sa.String(64), nullable=False),
            sa.Column("finance_review_id", sa.String(128), nullable=True),
            sa.Column("finance_review_revision", sa.Integer(), nullable=True),
            sa.Column("expected_generation", sa.Integer(), nullable=False),
            sa.Column("expected_selection_id", sa.String(128), nullable=True),
            sa.Column("idempotency_key", sa.String(256), nullable=False),
            sa.Column("request_fingerprint", sa.String(64), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("selection_id", name="pk_case_proposal_selections"),
            sa.UniqueConstraint(
                "idempotency_key", name="uq_case_proposal_selections_idempotency_key"
            ),
            sa.CheckConstraint(
                PAIR, name=op.f("ck_case_proposal_selections_review_pair")
            ),
            sa.CheckConstraint(
                "expected_generation >= 0",
                name=op.f("ck_case_proposal_selections_generation_nonnegative"),
            ),
            sa.CheckConstraint(
                "workflow_version = 'independent-finance-v1'",
                name=op.f("ck_case_proposal_selections_policy"),
            ),
            sa.ForeignKeyConstraint(
                ["case_id"],
                ["case_instances.case_id"],
                ondelete="RESTRICT",
                name="fk_case_proposal_selections_case_id_case_instances",
            ),
            sa.ForeignKeyConstraint(
                ["analysis_id"],
                ["analysis_versions.analysis_id"],
                ondelete="RESTRICT",
                name="fk_case_proposal_selections_analysis_id_analysis_versions",
            ),
            sa.ForeignKeyConstraint(
                ["expected_selection_id"],
                ["case_proposal_selections.selection_id"],
                ondelete="RESTRICT",
                name="fk_case_proposal_selections_expected_selection_id_case_proposal_selections",
            ),
            sa.ForeignKeyConstraint(
                ["finance_review_id", "finance_review_revision"],
                [
                    "finance_review_revisions.review_id",
                    "finance_review_revisions.revision",
                ],
                ondelete="RESTRICT",
                name="fk_case_proposal_selections_finance_review",
            ),
        )
    existing = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(JOURNAL)}
    for column in ("case_id", "analysis_id", "submitted_at"):
        name = f"ix_case_proposal_selections_{column}"
        if name not in existing:
            op.create_index(name, JOURNAL, [column])
    if "uq_case_proposal_selections_finance_review_id" not in existing:
        op.create_index(
            "uq_case_proposal_selections_finance_review_id",
            JOURNAL,
            ["finance_review_id"],
            unique=True,
            sqlite_where=sa.text("finance_review_id IS NOT NULL"),
            mssql_where=sa.text("finance_review_id IS NOT NULL"),
        )
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("case_projection")}
    fks = {f["name"] for f in inspector.get_foreign_keys("case_projection")}
    checks = {c["name"] for c in inspector.get_check_constraints("case_projection")}
    if (
        not {"proposal_generation", "current_selection_id"} <= columns
        or PROJECTION_FK not in fks
        or PROJECTION_CHECK not in checks
    ):
        with op.batch_alter_table("case_projection") as batch:
            if "proposal_generation" not in columns:
                batch.add_column(
                    sa.Column(
                        "proposal_generation",
                        sa.Integer(),
                        nullable=False,
                        server_default=sa.text("0"),
                    )
                )
            if "current_selection_id" not in columns:
                batch.add_column(
                    sa.Column("current_selection_id", sa.String(128), nullable=True)
                )
            if PROJECTION_FK not in fks:
                batch.create_foreign_key(
                    PROJECTION_FK,
                    JOURNAL,
                    ["current_selection_id"],
                    ["selection_id"],
                    ondelete="RESTRICT",
                )
            if PROJECTION_CHECK not in checks:
                batch.create_check_constraint(
                    op.f(PROJECTION_CHECK), "proposal_generation >= 0"
                )
    if "ix_case_projection_current_selection_id" not in {
        i["name"] for i in sa.inspect(op.get_bind()).get_indexes("case_projection")
    }:
        op.create_index(
            "ix_case_projection_current_selection_id",
            "case_projection",
            ["current_selection_id"],
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("case_projection")}
    fks = {f["name"] for f in inspector.get_foreign_keys("case_projection")}
    checks = {c["name"] for c in inspector.get_check_constraints("case_projection")}
    indexes = {i["name"] for i in inspector.get_indexes("case_projection")}
    if "ix_case_projection_current_selection_id" in indexes:
        op.drop_index(
            "ix_case_projection_current_selection_id", table_name="case_projection"
        )
    if {"proposal_generation", "current_selection_id"} & columns:
        with op.batch_alter_table("case_projection") as batch:
            if PROJECTION_FK in fks:
                batch.drop_constraint(PROJECTION_FK, type_="foreignkey")
            if PROJECTION_CHECK in checks:
                batch.drop_constraint(op.f(PROJECTION_CHECK), type_="check")
            if "current_selection_id" in columns:
                batch.drop_column("current_selection_id")
            if "proposal_generation" in columns:
                batch.drop_column("proposal_generation")
    if JOURNAL in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(JOURNAL)
