SET XACT_ABORT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'app')
    EXEC(N'CREATE SCHEMA app');
GO

CREATE TABLE app.schema_version (
    component nvarchar(64) NOT NULL,
    schema_version int NOT NULL,
    applied_at datetimeoffset(6) NOT NULL
        CONSTRAINT df_schema_version_applied_at DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT pk_schema_version PRIMARY KEY (component)
);
GO

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
GO

CREATE INDEX ix_case_instances_template_id ON app.case_instances (template_id);
CREATE INDEX ix_case_instances_purpose ON app.case_instances (purpose);
CREATE INDEX ix_case_instances_runtime_mode ON app.case_instances (runtime_mode);
CREATE INDEX ix_case_instances_status ON app.case_instances (status);
CREATE INDEX ix_case_instances_scenario_time
    ON app.case_instances (scenario_effective_time);
GO

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
GO

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
GO

CREATE INDEX ix_analysis_versions_case_id ON app.analysis_versions (case_id);
CREATE INDEX ix_analysis_versions_material_hash ON app.analysis_versions (material_hash);
CREATE INDEX ix_analysis_versions_created_at ON app.analysis_versions (created_at);
GO

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
GO

CREATE INDEX ix_evidence_items_analysis_id ON app.evidence_items (analysis_id);
CREATE INDEX ix_evidence_items_case_id ON app.evidence_items (case_id);
GO

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
GO

CREATE INDEX ix_decisions_case_id ON app.decisions (case_id);
CREATE INDEX ix_decisions_analysis_id ON app.decisions (analysis_id);
CREATE INDEX ix_decisions_decided_at ON app.decisions (decided_at);
GO

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
GO

CREATE INDEX ix_approval_satisfactions_decision_id
    ON app.approval_satisfactions (decision_id);
GO

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
GO

CREATE INDEX ix_outbox_claim_ready
    ON app.outbox_events (claim_status, available_at);
GO

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
GO

CREATE INDEX ix_execution_actions_decision_id
    ON app.execution_actions (decision_id);
GO

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
GO

CREATE INDEX ix_action_projection_decision_id ON app.action_projection (decision_id);
CREATE INDEX ix_action_projection_status ON app.action_projection (status);
GO

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
GO

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
GO

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
GO

CREATE TABLE app.playbacks (
    playback_id nvarchar(128) NOT NULL,
    case_id nvarchar(128) NOT NULL,
    decision_id nvarchar(128) NOT NULL,
    status nvarchar(32) NOT NULL,
    started_at datetimeoffset(6) NOT NULL,
    completed_at datetimeoffset(6) NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_playbacks PRIMARY KEY (playback_id),
    CONSTRAINT uq_playback_per_decision UNIQUE (decision_id),
    CONSTRAINT fk_playbacks_case FOREIGN KEY (case_id)
        REFERENCES app.case_instances (case_id),
    CONSTRAINT fk_playbacks_decision FOREIGN KEY (decision_id)
        REFERENCES app.decisions (decision_id),
    CONSTRAINT ck_playbacks_payload_json CHECK (ISJSON(payload_json) = 1)
);
GO

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
GO

CREATE INDEX ix_outcome_observations_decision_id
    ON app.outcome_observations (decision_id);
CREATE INDEX ix_outcome_observations_action_id
    ON app.outcome_observations (action_id);
CREATE INDEX ix_outcome_observations_metric
    ON app.outcome_observations (metric);
GO

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
GO

CREATE INDEX ix_case_projection_purpose_status
    ON app.case_projection (purpose, status);
CREATE INDEX ix_case_projection_current_analysis_id
    ON app.case_projection (current_analysis_id);
CREATE INDEX ix_case_projection_current_decision_id
    ON app.case_projection (current_decision_id);
GO

INSERT INTO app.schema_version (component, schema_version)
VALUES (N'operational', 11);
GO
