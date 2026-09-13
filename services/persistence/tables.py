from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


case_instances = Table(
    "case_instances",
    metadata,
    Column("case_id", String(128), primary_key=True),
    Column("template_id", String(128), nullable=False, index=True),
    Column("purpose", String(32), nullable=False, index=True),
    Column("runtime_mode", String(16), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column(
        "scenario_effective_time", DateTime(timezone=True), nullable=False, index=True
    ),
    Column(
        "recorded_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    ),
    Column("payload_json", Text, nullable=False),
)

operational_snapshots = Table(
    "operational_snapshots",
    metadata,
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        primary_key=True,
    ),
    Column("runtime_mode", String(16), nullable=False, index=True),
    Column(
        "scenario_effective_time", DateTime(timezone=True), nullable=False, index=True
    ),
    Column(
        "analysis_horizon_start", DateTime(timezone=True), nullable=False, index=True
    ),
    Column("analysis_horizon_end", String(10), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
)

analysis_claims = Table(
    "analysis_claims",
    metadata,
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        primary_key=True,
    ),
    Column("material_version", String(128), primary_key=True),
    Column("claim_id", String(128), nullable=False, unique=True),
    Column("claimed_at", DateTime(timezone=True), nullable=False, index=True),
    Column("claim_expires_at", DateTime(timezone=True), nullable=False, index=True),
)

case_proposal_selections = Table(
    "case_proposal_selections",
    metadata,
    Column("selection_id", String(128), primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column(
        "analysis_id",
        String(128),
        ForeignKey("analysis_versions.analysis_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("analysis_material_hash", String(64), nullable=False),
    Column("workflow_version", String(64), nullable=False),
    Column("finance_review_id", String(128), nullable=True),
    Column("finance_review_revision", Integer, nullable=True),
    Column("expected_generation", Integer, nullable=False),
    Column(
        "expected_selection_id",
        String(128),
        ForeignKey("case_proposal_selections.selection_id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("idempotency_key", String(256), nullable=False, unique=True),
    Column("request_fingerprint", String(64), nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    ForeignKeyConstraint(
        ["finance_review_id", "finance_review_revision"],
        ["finance_review_revisions.review_id", "finance_review_revisions.revision"],
        ondelete="RESTRICT",
        name="fk_case_proposal_selections_finance_review",
    ),
    CheckConstraint(
        "(finance_review_id IS NULL AND finance_review_revision IS NULL) OR (finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL AND finance_review_revision = 1)",
        name="review_pair",
    ),
    CheckConstraint("expected_generation >= 0", name="generation_nonnegative"),
    CheckConstraint("workflow_version = 'independent-finance-v1'", name="policy"),
)
Index(
    "uq_case_proposal_selections_finance_review_id",
    case_proposal_selections.c.finance_review_id,
    unique=True,
    sqlite_where=text("finance_review_id IS NOT NULL"),
    mssql_where=text("finance_review_id IS NOT NULL"),
)

case_projection = Table(
    "case_projection",
    metadata,
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        primary_key=True,
    ),
    Column("purpose", String(32), nullable=False, index=True),
    Column("runtime_mode", String(16), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column(
        "scenario_effective_time", DateTime(timezone=True), nullable=False, index=True
    ),
    Column(
        "current_analysis_id",
        String(128),
        ForeignKey("analysis_versions.analysis_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    ),
    Column("current_analysis_hash", String(128), nullable=True, index=True),
    Column("proposal_generation", Integer, nullable=False, server_default=text("0")),
    Column(
        "current_selection_id",
        String(128),
        ForeignKey("case_proposal_selections.selection_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    ),
    Column(
        "current_decision_id",
        String(128),
        ForeignKey("decisions.decision_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    ),
    Column("payload_json", Text, nullable=False),
    CheckConstraint("proposal_generation >= 0", name="proposal_generation_nonnegative"),
)

analysis_versions = Table(
    "analysis_versions",
    metadata,
    Column("analysis_id", String(128), primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        nullable=False,
        index=True,
    ),
    Column("material_hash", String(128), nullable=False, index=True),
    Column("runtime_mode", String(16), nullable=False, index=True),
    Column("analysis_started_at", DateTime(timezone=True), nullable=False, index=True),
    Column(
        "retrieval_window_ends_at", DateTime(timezone=True), nullable=False, index=True
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
)

finance_review_revisions = Table(
    "finance_review_revisions",
    metadata,
    Column("review_id", String(128), primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column(
        "analysis_id",
        String(128),
        ForeignKey("analysis_versions.analysis_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("analysis_material_hash", String(64), nullable=False, index=True),
    Column("option_id", String(128), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column("idempotency_key", String(256), nullable=False),
    Column("request_fingerprint", String(64), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint(
        "idempotency_key", name="uq_finance_review_revisions_idempotency_key"
    ),
    CheckConstraint("revision > 0", name="revision_positive"),
)

evidence_items = Table(
    "evidence_items",
    metadata,
    Column("evidence_id", String(128), primary_key=True),
    Column(
        "analysis_id",
        String(128),
        ForeignKey("analysis_versions.analysis_id"),
        primary_key=True,
    ),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        nullable=False,
        index=True,
    ),
    Column("kind", String(64), nullable=False, index=True),
    Column("runtime_mode", String(16), nullable=False, index=True),
    Column("source_system", String(64), nullable=False, index=True),
    Column("source_timestamp", DateTime(timezone=True), nullable=True, index=True),
    Column("retrieved_at", DateTime(timezone=True), nullable=True, index=True),
    Column("effective_at", DateTime(timezone=True), nullable=True, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=True, index=True),
    Column("payload_json", Text, nullable=False),
)

decisions = Table(
    "decisions",
    metadata,
    Column("decision_id", String(128), primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "analysis_id",
        String(128),
        ForeignKey("analysis_versions.analysis_id"),
        nullable=False,
        index=True,
    ),
    Column("idempotency_key", String(256), nullable=False, unique=True),
    Column("kind", String(32), nullable=False, index=True),
    Column("runtime_mode", String(16), nullable=False, index=True),
    Column("decided_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
)

approval_satisfactions = Table(
    "approval_satisfactions",
    metadata,
    Column("approval_satisfaction_id", Integer, primary_key=True, autoincrement=True),
    Column(
        "analysis_id",
        String(128),
        ForeignKey("analysis_versions.analysis_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=True,
        index=True,
    ),
    Column("option_id", String(128), nullable=False, index=True),
    Column("authorization_id", String(128), nullable=False, index=True),
    Column("persona_id", String(128), nullable=False, index=True),
    Column("role", String(128), nullable=False, index=True),
    Column("satisfied", Boolean, nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint(
        "analysis_id",
        "decision_id",
        "option_id",
        "authorization_id",
        "persona_id",
        "role",
        name="uq_approval_satisfaction_material",
    ),
)

outbox_events = Table(
    "outbox_events",
    metadata,
    Column("event_id", String(128), primary_key=True),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("event_type", String(128), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("available_at", DateTime(timezone=True), nullable=False, index=True),
    Column("claim_status", String(32), nullable=False, index=True),
    Column("claimed_by", String(128), nullable=True, index=True),
    Column("claimed_at", DateTime(timezone=True), nullable=True, index=True),
    Column("claim_expires_at", DateTime(timezone=True), nullable=True, index=True),
    Column("processed_at", DateTime(timezone=True), nullable=True, index=True),
    Column("attempt_count", Integer, nullable=False, server_default=text("0")),
    Column("last_error", Text, nullable=True),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint(
        "decision_id",
        "event_type",
        name="uq_outbox_event_per_decision",
    ),
)

execution_actions = Table(
    "execution_actions",
    metadata,
    Column("action_id", String(128), primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("action_kind", String(64), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
)

action_projection = Table(
    "action_projection",
    metadata,
    Column(
        "action_id",
        String(128),
        ForeignKey("execution_actions.action_id"),
        primary_key=True,
    ),
    Column("case_id", String(128), nullable=False, index=True),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("status", String(32), nullable=False, index=True),
    Column("current_attempt", Integer, nullable=False, server_default=text("0")),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    ),
    Column("payload_json", Text, nullable=False),
)

draft_artifacts = Table(
    "draft_artifacts",
    metadata,
    Column("artifact_id", String(128), primary_key=True),
    Column(
        "action_id",
        String(128),
        ForeignKey("execution_actions.action_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("artifact_kind", String(64), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
)

execution_events = Table(
    "execution_events",
    metadata,
    Column("execution_event_id", String(128), primary_key=True),
    Column(
        "action_id",
        String(128),
        ForeignKey("execution_actions.action_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("event_type", String(64), nullable=False, index=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
)

execution_attempts = Table(
    "execution_attempts",
    metadata,
    Column("attempt_id", String(128), primary_key=True),
    Column(
        "action_id",
        String(128),
        ForeignKey("execution_actions.action_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("attempt_number", Integer, nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("started_at", DateTime(timezone=True), nullable=False, index=True),
    Column("completed_at", DateTime(timezone=True), nullable=True, index=True),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint(
        "action_id",
        "attempt_number",
        name="uq_execution_attempt_action_number",
    ),
)

playbacks = Table(
    "playbacks",
    metadata,
    Column("playback_id", String(128), primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column("status", String(32), nullable=False, index=True),
    Column("started_at", DateTime(timezone=True), nullable=False, index=True),
    Column("completed_at", DateTime(timezone=True), nullable=True, index=True),
    Column("failed_at", DateTime(timezone=True), nullable=True, index=True),
    Column("error_code", String(64), nullable=True),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint("decision_id", name="uq_playback_per_decision"),
)

outcome_observations = Table(
    "outcome_observations",
    metadata,
    Column("observation_id", String(128), primary_key=True),
    Column(
        "case_id",
        String(128),
        ForeignKey("case_instances.case_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "decision_id",
        String(128),
        ForeignKey("decisions.decision_id"),
        nullable=False,
        index=True,
    ),
    Column(
        "playback_id",
        String(128),
        ForeignKey("playbacks.playback_id"),
        nullable=True,
        index=True,
    ),
    Column(
        "action_id",
        String(128),
        ForeignKey("execution_actions.action_id"),
        nullable=True,
        index=True,
    ),
    Column("metric", String(128), nullable=False, index=True),
    Column("observed_value", String(128), nullable=False),
    Column("unit", String(32), nullable=False),
    Column("predicted_value", String(128), nullable=False),
    Column(
        "scenario_effective_time", DateTime(timezone=True), nullable=False, index=True
    ),
    Column("scenario_timezone", String(64), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False, index=True),
    Column("source_reference", String(256), nullable=False),
    Column("kind", String(32), nullable=False, index=True),
    Column("synthetic", Boolean, nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    CheckConstraint(
        "(kind = 'simulated' AND synthetic = 1) OR (kind = 'actual' AND synthetic = 0)",
        name="observation_kind_synthetic_provenance",
    ),
)


Index(
    "ix_case_projection_purpose_status",
    case_projection.c.purpose,
    case_projection.c.status,
)
Index(
    "ix_outbox_claim_ready", outbox_events.c.claim_status, outbox_events.c.available_at
)
