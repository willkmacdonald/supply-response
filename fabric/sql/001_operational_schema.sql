SET XACT_ABORT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'app')
    EXEC(N'CREATE SCHEMA app');
GO

IF OBJECT_ID(N'app.schema_version', N'U') IS NULL
BEGIN
CREATE TABLE app.schema_version (
    component nvarchar(64) NOT NULL,
    schema_version int NOT NULL,
    applied_at datetimeoffset(6) NOT NULL
        CONSTRAINT df_schema_version_applied_at DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT pk_schema_version PRIMARY KEY (component)
);
END;
GO

IF OBJECT_ID(N'app.case_instances', N'U') IS NULL
BEGIN
CREATE TABLE app.case_instances (
    case_id nvarchar(128) NOT NULL,
    template_id nvarchar(128) NOT NULL,
    purpose nvarchar(32) NOT NULL,
    runtime_mode nvarchar(16) NOT NULL,
    status nvarchar(32) NOT NULL,
    scenario_effective_time datetimeoffset(6) NOT NULL,
    recorded_at datetimeoffset(6) NOT NULL
        CONSTRAINT df_case_instances_recorded_at DEFAULT SYSDATETIMEOFFSET(),
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_case_instances PRIMARY KEY (case_id),
    CONSTRAINT ck_case_instances_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_instances') AND name = N'ix_case_instances_template_id')
    CREATE INDEX ix_case_instances_template_id ON app.case_instances (template_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_instances') AND name = N'ix_case_instances_purpose')
    CREATE INDEX ix_case_instances_purpose ON app.case_instances (purpose);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_instances') AND name = N'ix_case_instances_runtime_mode')
    CREATE INDEX ix_case_instances_runtime_mode ON app.case_instances (runtime_mode);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_instances') AND name = N'ix_case_instances_status')
    CREATE INDEX ix_case_instances_status ON app.case_instances (status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_instances') AND name = N'ix_case_instances_scenario_time')
    CREATE INDEX ix_case_instances_scenario_time
    ON app.case_instances (scenario_effective_time);
GO

IF OBJECT_ID(N'app.operational_snapshots', N'U') IS NULL
BEGIN
CREATE TABLE app.operational_snapshots (
    case_id nvarchar(128) NOT NULL,
    runtime_mode nvarchar(16) NOT NULL,
    scenario_effective_time datetimeoffset(6) NOT NULL,
    analysis_horizon_start datetimeoffset(6) NOT NULL,
    analysis_horizon_end nvarchar(10) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_operational_snapshots PRIMARY KEY (case_id),
    CONSTRAINT fk_operational_snapshots_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT ck_operational_snapshots_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF OBJECT_ID(N'app.analysis_versions', N'U') IS NULL
BEGIN
CREATE TABLE app.analysis_versions (
    analysis_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    material_hash nvarchar(128) NOT NULL,
    runtime_mode nvarchar(16) NOT NULL,
    analysis_started_at datetimeoffset(6) NOT NULL,
    retrieval_window_ends_at datetimeoffset(6) NOT NULL,
    created_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_analysis_versions PRIMARY KEY (analysis_id),
    CONSTRAINT fk_analysis_versions_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT ck_analysis_versions_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.analysis_versions') AND name = N'ix_analysis_versions_case_id')
    CREATE INDEX ix_analysis_versions_case_id ON app.analysis_versions (case_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.analysis_versions') AND name = N'ix_analysis_versions_material_hash')
    CREATE INDEX ix_analysis_versions_material_hash ON app.analysis_versions (material_hash);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.analysis_versions') AND name = N'ix_analysis_versions_created_at')
    CREATE INDEX ix_analysis_versions_created_at ON app.analysis_versions (created_at);
GO

IF OBJECT_ID(N'app.finance_review_revisions', N'U') IS NULL
BEGIN
CREATE TABLE app.finance_review_revisions (
    review_id nvarchar(128) NOT NULL,
    revision int NOT NULL,
    case_id nvarchar(128) NOT NULL,
    analysis_id nvarchar(128) NOT NULL,
    analysis_material_hash nvarchar(64) NOT NULL,
    option_id nvarchar(128) NOT NULL,
    status nvarchar(32) NOT NULL,
    idempotency_key nvarchar(256) NOT NULL,
    request_fingerprint nvarchar(64) NOT NULL,
    recorded_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_finance_review_revisions PRIMARY KEY (review_id, revision),
    CONSTRAINT uq_finance_review_revisions_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_finance_review_revisions_revision_positive CHECK (revision > 0),
    CONSTRAINT ck_finance_review_revisions_payload_json CHECK (ISJSON(payload_json) = 1),
    CONSTRAINT fk_finance_review_revisions_case FOREIGN KEY (case_id) REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_finance_review_revisions_analysis FOREIGN KEY (analysis_id) REFERENCES app.analysis_versions (analysis_id)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.finance_review_revisions') AND name = N'ix_finance_review_revisions_case_id') CREATE INDEX ix_finance_review_revisions_case_id ON app.finance_review_revisions (case_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.finance_review_revisions') AND name = N'ix_finance_review_revisions_analysis_id') CREATE INDEX ix_finance_review_revisions_analysis_id ON app.finance_review_revisions (analysis_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.finance_review_revisions') AND name = N'ix_finance_review_revisions_analysis_material_hash') CREATE INDEX ix_finance_review_revisions_analysis_material_hash ON app.finance_review_revisions (analysis_material_hash);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.finance_review_revisions') AND name = N'ix_finance_review_revisions_option_id') CREATE INDEX ix_finance_review_revisions_option_id ON app.finance_review_revisions (option_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.finance_review_revisions') AND name = N'ix_finance_review_revisions_status') CREATE INDEX ix_finance_review_revisions_status ON app.finance_review_revisions (status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.finance_review_revisions') AND name = N'ix_finance_review_revisions_recorded_at') CREATE INDEX ix_finance_review_revisions_recorded_at ON app.finance_review_revisions (recorded_at);
GO

IF OBJECT_ID(N'app.case_proposal_selections', N'U') IS NULL
BEGIN
CREATE TABLE app.case_proposal_selections (
    selection_id nvarchar(128) NOT NULL, case_id nvarchar(128) NOT NULL,
    analysis_id nvarchar(128) NOT NULL, analysis_material_hash nvarchar(64) NOT NULL,
    workflow_version nvarchar(64) NOT NULL, finance_review_id nvarchar(128) NULL,
    finance_review_revision int NULL, expected_generation int NOT NULL,
    expected_selection_id nvarchar(128) NULL, idempotency_key nvarchar(256) NOT NULL,
    request_fingerprint nvarchar(64) NOT NULL, submitted_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_case_proposal_selections PRIMARY KEY (selection_id),
    CONSTRAINT uq_case_proposal_selections_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_case_proposal_selections_review_pair CHECK ((finance_review_id IS NULL AND finance_review_revision IS NULL) OR (finance_review_id IS NOT NULL AND finance_review_revision IS NOT NULL AND finance_review_revision = 1)),
    CONSTRAINT ck_case_proposal_selections_generation_nonnegative CHECK (expected_generation >= 0),
    CONSTRAINT ck_case_proposal_selections_policy CHECK (workflow_version = N'independent-finance-v1'),
    CONSTRAINT ck_case_proposal_selections_payload_json CHECK (ISJSON(payload_json) = 1),
    CONSTRAINT fk_case_proposal_selections_case_id_case_instances FOREIGN KEY (case_id) REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_case_proposal_selections_analysis_id_analysis_versions FOREIGN KEY (analysis_id) REFERENCES app.analysis_versions (analysis_id),
    CONSTRAINT fk_case_proposal_selections_expected_selection_id_case_proposal_selections FOREIGN KEY (expected_selection_id) REFERENCES app.case_proposal_selections (selection_id),
    CONSTRAINT fk_case_proposal_selections_finance_review FOREIGN KEY (finance_review_id, finance_review_revision) REFERENCES app.finance_review_revisions (review_id, revision)
);
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'ix_case_proposal_selections_case_id') CREATE INDEX ix_case_proposal_selections_case_id ON app.case_proposal_selections (case_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'ix_case_proposal_selections_analysis_id') CREATE INDEX ix_case_proposal_selections_analysis_id ON app.case_proposal_selections (analysis_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'ix_case_proposal_selections_submitted_at') CREATE INDEX ix_case_proposal_selections_submitted_at ON app.case_proposal_selections (submitted_at);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_proposal_selections') AND name = N'uq_case_proposal_selections_finance_review_id') CREATE UNIQUE INDEX uq_case_proposal_selections_finance_review_id ON app.case_proposal_selections (finance_review_id) WHERE finance_review_id IS NOT NULL;
GO

IF OBJECT_ID(N'app.evidence_items', N'U') IS NULL
BEGIN
CREATE TABLE app.evidence_items (
    evidence_id nvarchar(128) NOT NULL,
    analysis_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    kind nvarchar(64) NOT NULL,
    runtime_mode nvarchar(16) NOT NULL,
    source_system nvarchar(64) NOT NULL,
    source_timestamp datetimeoffset(6) NULL,
    retrieved_at datetimeoffset(6) NULL,
    effective_at datetimeoffset(6) NULL,
    expires_at datetimeoffset(6) NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_evidence_items PRIMARY KEY (evidence_id, analysis_id),
    CONSTRAINT fk_evidence_items_analysis FOREIGN KEY (analysis_id)
        REFERENCES app.analysis_versions (analysis_id),
    CONSTRAINT fk_evidence_items_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT ck_evidence_items_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.evidence_items') AND name = N'ix_evidence_items_analysis_id')
    CREATE INDEX ix_evidence_items_analysis_id ON app.evidence_items (analysis_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.evidence_items') AND name = N'ix_evidence_items_case_id')
    CREATE INDEX ix_evidence_items_case_id ON app.evidence_items (case_id);
GO

IF OBJECT_ID(N'app.decisions', N'U') IS NULL
BEGIN
CREATE TABLE app.decisions (
    decision_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    analysis_id nvarchar(128) NOT NULL,
    idempotency_key nvarchar(256) NOT NULL,
    kind nvarchar(32) NOT NULL,
    runtime_mode nvarchar(16) NOT NULL,
    decided_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_decisions PRIMARY KEY (decision_id),
    CONSTRAINT uq_decisions_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT fk_decisions_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_decisions_analysis FOREIGN KEY (analysis_id)
        REFERENCES app.analysis_versions (analysis_id),
    CONSTRAINT ck_decisions_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.decisions') AND name = N'ix_decisions_case_id')
    CREATE INDEX ix_decisions_case_id ON app.decisions (case_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.decisions') AND name = N'ix_decisions_analysis_id')
    CREATE INDEX ix_decisions_analysis_id ON app.decisions (analysis_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.decisions') AND name = N'ix_decisions_decided_at')
    CREATE INDEX ix_decisions_decided_at ON app.decisions (decided_at);
GO

IF OBJECT_ID(N'app.approval_satisfactions', N'U') IS NULL
BEGIN
CREATE TABLE app.approval_satisfactions (
    approval_satisfaction_id bigint IDENTITY(1,1) NOT NULL,
    analysis_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NULL,
    option_id nvarchar(128) NOT NULL,
    authorization_id nvarchar(128) NOT NULL,
    persona_id nvarchar(128) NOT NULL,
    role nvarchar(128) NOT NULL,
    satisfied bit NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_approval_satisfactions PRIMARY KEY (approval_satisfaction_id),
    CONSTRAINT fk_approval_satisfactions_analysis FOREIGN KEY (analysis_id)
        REFERENCES app.analysis_versions (analysis_id),
    CONSTRAINT fk_approval_satisfactions_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT uq_approval_satisfaction_material UNIQUE (
        analysis_id, decision_id, option_id, authorization_id, persona_id, role
    ),
    CONSTRAINT ck_approval_satisfactions_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.approval_satisfactions') AND name = N'ix_approval_satisfactions_decision_id')
    CREATE INDEX ix_approval_satisfactions_decision_id
    ON app.approval_satisfactions (decision_id);
GO

IF OBJECT_ID(N'app.outbox_events', N'U') IS NULL
BEGIN
CREATE TABLE app.outbox_events (
    event_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    event_type nvarchar(128) NOT NULL,
    created_at datetimeoffset(6) NOT NULL,
    available_at datetimeoffset(6) NOT NULL,
    claim_status nvarchar(32) NOT NULL,
    claimed_by nvarchar(128) NULL,
    claimed_at datetimeoffset(6) NULL,
    claim_expires_at datetimeoffset(6) NULL,
    processed_at datetimeoffset(6) NULL,
    attempt_count int NOT NULL CONSTRAINT df_outbox_attempt_count DEFAULT 0,
    last_error nvarchar(max) NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_outbox_events PRIMARY KEY (event_id),
    CONSTRAINT uq_outbox_event_per_decision UNIQUE (decision_id, event_type),
    CONSTRAINT fk_outbox_events_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_outbox_events_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.outbox_events') AND name = N'ix_outbox_claim_ready')
    CREATE INDEX ix_outbox_claim_ready
    ON app.outbox_events (claim_status, available_at);
GO

IF OBJECT_ID(N'app.execution_actions', N'U') IS NULL
BEGIN
CREATE TABLE app.execution_actions (
    action_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    action_kind nvarchar(64) NOT NULL,
    status nvarchar(32) NOT NULL,
    created_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_execution_actions PRIMARY KEY (action_id),
    CONSTRAINT fk_execution_actions_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_execution_actions_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_execution_actions_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.execution_actions') AND name = N'ix_execution_actions_decision_id')
    CREATE INDEX ix_execution_actions_decision_id
    ON app.execution_actions (decision_id);
GO

IF OBJECT_ID(N'app.action_projection', N'U') IS NULL
BEGIN
CREATE TABLE app.action_projection (
    action_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    status nvarchar(32) NOT NULL,
    current_attempt int NOT NULL CONSTRAINT df_action_current_attempt DEFAULT 0,
    updated_at datetimeoffset(6) NOT NULL
        CONSTRAINT df_action_projection_updated_at DEFAULT SYSDATETIMEOFFSET(),
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_action_projection PRIMARY KEY (action_id),
    CONSTRAINT fk_action_projection_action FOREIGN KEY (action_id)
        REFERENCES app.execution_actions (action_id),
    CONSTRAINT fk_action_projection_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_action_projection_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.action_projection') AND name = N'ix_action_projection_decision_id')
    CREATE INDEX ix_action_projection_decision_id ON app.action_projection (decision_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.action_projection') AND name = N'ix_action_projection_status')
    CREATE INDEX ix_action_projection_status ON app.action_projection (status);
GO

IF OBJECT_ID(N'app.draft_artifacts', N'U') IS NULL
BEGIN
CREATE TABLE app.draft_artifacts (
    artifact_id nvarchar(128) NOT NULL,
    action_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    artifact_kind nvarchar(64) NOT NULL,
    created_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_draft_artifacts PRIMARY KEY (artifact_id),
    CONSTRAINT fk_draft_artifacts_action FOREIGN KEY (action_id)
        REFERENCES app.execution_actions (action_id),
    CONSTRAINT fk_draft_artifacts_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_draft_artifacts_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF OBJECT_ID(N'app.execution_attempts', N'U') IS NULL
BEGIN
CREATE TABLE app.execution_attempts (
    attempt_id nvarchar(128) NOT NULL,
    action_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    attempt_number int NOT NULL,
    status nvarchar(32) NOT NULL,
    started_at datetimeoffset(6) NOT NULL,
    completed_at datetimeoffset(6) NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_execution_attempts PRIMARY KEY (attempt_id),
    CONSTRAINT uq_execution_attempt_action_number UNIQUE (action_id, attempt_number),
    CONSTRAINT fk_execution_attempts_action FOREIGN KEY (action_id)
        REFERENCES app.execution_actions (action_id),
    CONSTRAINT fk_execution_attempts_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_execution_attempts_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF OBJECT_ID(N'app.execution_events', N'U') IS NULL
BEGIN
CREATE TABLE app.execution_events (
    execution_event_id nvarchar(128) NOT NULL,
    action_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    event_type nvarchar(64) NOT NULL,
    occurred_at datetimeoffset(6) NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_execution_events PRIMARY KEY (execution_event_id),
    CONSTRAINT fk_execution_events_action FOREIGN KEY (action_id)
        REFERENCES app.execution_actions (action_id),
    CONSTRAINT fk_execution_events_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_execution_events_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF OBJECT_ID(N'app.playbacks', N'U') IS NULL
BEGIN
CREATE TABLE app.playbacks (
    playback_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    status nvarchar(32) NOT NULL,
    started_at datetimeoffset(6) NOT NULL,
    completed_at datetimeoffset(6) NULL,
    failed_at datetimeoffset(6) NULL,
    error_code nvarchar(64) NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_playbacks PRIMARY KEY (playback_id),
    CONSTRAINT uq_playback_per_decision UNIQUE (decision_id),
    CONSTRAINT fk_playbacks_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_playbacks_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_playbacks_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF COL_LENGTH(N'app.playbacks', N'failed_at') IS NULL
    ALTER TABLE app.playbacks ADD failed_at datetimeoffset(6) NULL;
GO

IF COL_LENGTH(N'app.playbacks', N'error_code') IS NULL
    ALTER TABLE app.playbacks ADD error_code nvarchar(64) NULL;
GO

IF OBJECT_ID(N'app.outcome_observations', N'U') IS NULL
BEGIN
CREATE TABLE app.outcome_observations (
    observation_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    playback_id nvarchar(128) NULL,
    action_id nvarchar(128) NULL,
    metric nvarchar(128) NOT NULL,
    observed_value nvarchar(128) NOT NULL,
    unit nvarchar(32) NOT NULL,
    predicted_value nvarchar(128) NOT NULL,
    scenario_effective_time datetimeoffset(6) NOT NULL,
    scenario_timezone nvarchar(64) NOT NULL,
    recorded_at datetimeoffset(6) NOT NULL,
    source_reference nvarchar(256) NOT NULL,
    kind nvarchar(32) NOT NULL,
    synthetic bit NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_outcome_observations PRIMARY KEY (observation_id),
    CONSTRAINT fk_outcome_observations_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_outcome_observations_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT fk_outcome_observations_playback FOREIGN KEY (playback_id)
        REFERENCES app.playbacks (playback_id),
    CONSTRAINT fk_outcome_observations_action FOREIGN KEY (action_id)
        REFERENCES app.execution_actions (action_id),
    CONSTRAINT ck_observation_kind_synthetic CHECK (
        (kind = N'simulated' AND synthetic = 1)
        OR (kind = N'actual' AND synthetic = 0)
    ),
    CONSTRAINT ck_outcome_observations_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.outcome_observations') AND name = N'ix_outcome_observations_decision_id')
    CREATE INDEX ix_outcome_observations_decision_id
    ON app.outcome_observations (decision_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.outcome_observations') AND name = N'ix_outcome_observations_action_id')
    CREATE INDEX ix_outcome_observations_action_id
    ON app.outcome_observations (action_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.outcome_observations') AND name = N'ix_outcome_observations_metric')
    CREATE INDEX ix_outcome_observations_metric
    ON app.outcome_observations (metric);
GO

IF OBJECT_ID(N'app.case_projection', N'U') IS NULL
BEGIN
CREATE TABLE app.case_projection (
    case_id nvarchar(128) NOT NULL,
    purpose nvarchar(32) NOT NULL,
    runtime_mode nvarchar(16) NOT NULL,
    status nvarchar(32) NOT NULL,
    scenario_effective_time datetimeoffset(6) NOT NULL,
    current_analysis_id nvarchar(128) NULL,
    current_analysis_hash nvarchar(128) NULL,
    current_decision_id nvarchar(128) NULL,
    updated_at datetimeoffset(6) NOT NULL
        CONSTRAINT df_case_projection_updated_at DEFAULT SYSDATETIMEOFFSET(),
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_case_projection PRIMARY KEY (case_id),
    CONSTRAINT fk_case_projection_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_case_projection_analysis FOREIGN KEY (current_analysis_id)
        REFERENCES app.analysis_versions (analysis_id),
    CONSTRAINT fk_case_projection_decision FOREIGN KEY (current_decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_case_projection_payload_json CHECK (ISJSON(payload_json) = 1)
);
END;
GO

IF COL_LENGTH(N'app.case_projection', N'proposal_generation') IS NULL
    ALTER TABLE app.case_projection ADD proposal_generation int NOT NULL CONSTRAINT df_case_projection_proposal_generation DEFAULT (0) WITH VALUES;
GO
IF COL_LENGTH(N'app.case_projection', N'current_selection_id') IS NULL
    ALTER TABLE app.case_projection ADD current_selection_id nvarchar(128) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'app.case_projection') AND name = N'ck_case_projection_proposal_generation_nonnegative')
    ALTER TABLE app.case_projection ADD CONSTRAINT ck_case_projection_proposal_generation_nonnegative CHECK (proposal_generation >= 0);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(N'app.case_projection') AND name = N'fk_case_projection_current_selection_id_case_proposal_selections')
    ALTER TABLE app.case_projection ADD CONSTRAINT fk_case_projection_current_selection_id_case_proposal_selections FOREIGN KEY (current_selection_id) REFERENCES app.case_proposal_selections (selection_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_projection') AND name = N'ix_case_projection_current_selection_id')
    CREATE INDEX ix_case_projection_current_selection_id ON app.case_projection (current_selection_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_projection') AND name = N'ix_case_projection_purpose_status')
    CREATE INDEX ix_case_projection_purpose_status
    ON app.case_projection (purpose, status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_projection') AND name = N'ix_case_projection_current_analysis_id')
    CREATE INDEX ix_case_projection_current_analysis_id
    ON app.case_projection (current_analysis_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.case_projection') AND name = N'ix_case_projection_current_decision_id')
    CREATE INDEX ix_case_projection_current_decision_id
    ON app.case_projection (current_decision_id);
GO

IF OBJECT_ID(N'app.analysis_claims', N'U') IS NULL
BEGIN
CREATE TABLE app.analysis_claims (
    case_id nvarchar(128) NOT NULL,
    material_version nvarchar(128) NOT NULL,
    claim_id nvarchar(128) NOT NULL,
    claimed_at datetimeoffset(6) NOT NULL,
    claim_expires_at datetimeoffset(6) NOT NULL,
    CONSTRAINT pk_analysis_claims PRIMARY KEY (case_id, material_version),
    CONSTRAINT uq_analysis_claims_claim_id UNIQUE (claim_id),
    CONSTRAINT fk_analysis_claims_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.analysis_claims') AND name = N'ix_analysis_claims_claim_expires_at')
    CREATE INDEX ix_analysis_claims_claim_expires_at
    ON app.analysis_claims (claim_expires_at);
GO

IF OBJECT_ID(N'app.live_operational_sources', N'U') IS NULL
BEGIN
CREATE TABLE app.live_operational_sources (
    source_snapshot_id nvarchar(128) NOT NULL,
    template_id nvarchar(128) NOT NULL,
    effective_at datetimeoffset(6) NOT NULL,
    is_verified bit NOT NULL,
    snapshot_payload_json nvarchar(max) NOT NULL,
    evidence_payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_live_operational_sources PRIMARY KEY (source_snapshot_id),
    CONSTRAINT ck_live_operational_snapshot_json CHECK (ISJSON(snapshot_payload_json) = 1),
    CONSTRAINT ck_live_operational_evidence_json CHECK (ISJSON(evidence_payload_json) = 1)
);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'app.live_operational_sources') AND name = N'ix_live_operational_sources_current')
    CREATE INDEX ix_live_operational_sources_current
    ON app.live_operational_sources (template_id, is_verified, effective_at);
GO

MERGE app.schema_version WITH (HOLDLOCK) AS target
USING (
    SELECT N'operational' AS component, 11 AS schema_version
) AS source
ON target.component = source.component
WHEN MATCHED AND target.schema_version < source.schema_version THEN
    UPDATE SET
        schema_version = source.schema_version,
        applied_at = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN
    INSERT (component, schema_version)
    VALUES (source.component, source.schema_version);
GO
