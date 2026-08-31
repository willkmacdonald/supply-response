IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'analytics')
    EXEC(N'CREATE SCHEMA analytics');
GO

CREATE OR ALTER VIEW app.analysis_projection AS
SELECT
    a.analysis_id,
    a.case_id,
    JSON_VALUE(a.payload_json, '$.ranking.recommended_option_id')
        AS recommended_option_id,
    recommended.revenue_at_risk,
    recommended.otif_loss_percentage,
    a.created_at AS updated_at
FROM app.analysis_versions AS a
OUTER APPLY (
    SELECT TOP (1)
        option_value.revenue_at_risk,
        option_value.otif_loss_percentage
    FROM OPENJSON(a.payload_json, '$.response_options')
    WITH (
        option_id nvarchar(128) '$.option_id',
        revenue_at_risk decimal(19,4) '$.predicted.revenue_at_risk',
        otif_loss_percentage int '$.predicted.otif_loss_percentage'
    ) AS option_value
    WHERE option_value.option_id =
        JSON_VALUE(a.payload_json, '$.ranking.recommended_option_id')
) AS recommended;
GO

CREATE OR ALTER VIEW app.decision_projection AS
SELECT
    d.decision_id,
    d.case_id,
    d.analysis_id,
    d.kind,
    JSON_VALUE(d.payload_json, '$.selected_option_id') AS selected_option_id,
    TRY_CONVERT(
        datetimeoffset(6),
        JSON_VALUE(d.payload_json, '$.scenario_effective_time'),
        127
    ) AS scenario_effective_time,
    d.decided_at,
    d.decided_at AS updated_at
FROM app.decisions AS d;
GO

CREATE OR ALTER VIEW analytics.case_command_center AS
SELECT
    c.case_id,
    c.purpose,
    c.status,
    c.runtime_mode,
    c.scenario_effective_time,
    a.recommended_option_id,
    a.revenue_at_risk,
    a.otif_loss_percentage,
    d.decision_id,
    d.kind AS decision_kind,
    d.decided_at
FROM app.case_projection AS c
LEFT JOIN app.analysis_projection AS a
    ON a.analysis_id = c.current_analysis_id
LEFT JOIN app.decision_projection AS d
    ON d.decision_id = c.current_decision_id;
GO

CREATE OR ALTER VIEW analytics.action_outcomes AS
SELECT
    d.case_id,
    d.decision_id,
    d.selected_option_id,
    CAST('action' AS nvarchar(16)) AS record_type,
    x.action_id,
    action.action_kind,
    x.status AS action_status,
    CAST(NULL AS nvarchar(128)) AS metric,
    CAST(NULL AS nvarchar(128)) AS predicted_value,
    CAST(NULL AS nvarchar(128)) AS observed_value,
    CAST(NULL AS nvarchar(32)) AS unit,
    CAST(NULL AS nvarchar(32)) AS observation_kind,
    d.scenario_effective_time,
    x.updated_at AS projection_updated_at
FROM app.decision_projection AS d
JOIN app.action_projection AS x
    ON x.decision_id = d.decision_id
JOIN app.execution_actions AS action
    ON action.action_id = x.action_id
UNION ALL
SELECT
    d.case_id,
    d.decision_id,
    d.selected_option_id,
    CAST('observation' AS nvarchar(16)) AS record_type,
    o.action_id,
    CAST(NULL AS nvarchar(64)) AS action_kind,
    CAST(NULL AS nvarchar(32)) AS action_status,
    o.metric,
    o.predicted_value,
    o.observed_value,
    o.unit,
    o.kind AS observation_kind,
    o.scenario_effective_time,
    o.recorded_at AS projection_updated_at
FROM app.decision_projection AS d
JOIN app.outcome_observations AS o
    ON o.decision_id = d.decision_id;
GO

UPDATE app.schema_version
SET schema_version = 12,
    applied_at = SYSDATETIMEOFFSET()
WHERE component = N'operational'
  AND schema_version < 12;

IF NOT EXISTS (
    SELECT 1 FROM app.schema_version
    WHERE component = N'operational' AND schema_version >= 12
)
    THROW 51000, 'Operational schema version row is missing.', 1;
GO
