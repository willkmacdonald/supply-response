IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'analytics')
    EXEC(N'CREATE SCHEMA analytics');
GO

CREATE OR ALTER FUNCTION analytics.report_scalar
(@json nvarchar(max), @key nvarchar(128), @kind nvarchar(32))
RETURNS nvarchar(4000)
AS
BEGIN
    DECLARE @safe nvarchar(max)=CASE WHEN ISJSON(@json)=1
        AND LEFT(LTRIM(@json),1)=N'{' THEN @json ELSE N'{}' END;
    DECLARE @value nvarchar(max), @type int, @count int;
    SELECT @count=COUNT(*),@value=MAX([value]),@type=MAX([type])
    FROM OPENJSON(@safe) WHERE [key] COLLATE Latin1_General_100_BIN2=@key COLLATE Latin1_General_100_BIN2;
    IF @count<>1 RETURN NULL;
    IF LEFT(@kind,9)=N'nullable_'
    BEGIN
        IF @type=0 RETURN N'#null';
        SET @kind=SUBSTRING(@kind,10,32);
    END;
    IF @value IS NULL OR DATALENGTH(@value)>8000 RETURN NULL;
    IF @kind=N'text' AND @type=1 AND LEN(LTRIM(RTRIM(@value)))>0
       AND DATALENGTH(@value)=DATALENGTH(LTRIM(RTRIM(@value)))
       AND CHARINDEX(NCHAR(9),@value)=0 AND CHARINDEX(NCHAR(10),@value)=0
       AND CHARINDEX(NCHAR(13),@value)=0 RETURN @value;
    IF @kind=N'flag' AND @type=3 AND @value IN (N'true',N'false') RETURN @value;
    IF @kind=N'integer' AND @type=2 AND LEN(@value)>0
       AND @value COLLATE Latin1_General_100_BIN2 NOT LIKE N'%[^0-9]%'
       AND TRY_CONVERT(int,@value)>=0 RETURN @value;
    IF @kind=N'money' AND @type=1
    BEGIN
        IF LEN(@value)<4 RETURN NULL;
        IF DATALENGTH(@value)=2*LEN(@value)
           AND SUBSTRING(@value,LEN(@value)-2,1)=N'.'
           AND LEFT(@value,LEN(@value)-3) COLLATE Latin1_General_100_BIN2 NOT LIKE N'%[^0-9]%'
           AND RIGHT(@value,2) COLLATE Latin1_General_100_BIN2 NOT LIKE N'%[^0-9]%'
           AND TRY_CONVERT(decimal(19,4),@value) IS NOT NULL RETURN @value;
    END;
    IF @kind IN (N'date',N'instant') AND @type=1
    BEGIN
        DECLARE @day nvarchar(10)=LEFT(@value,10);
        IF DATALENGTH(@day)<>20 OR @day COLLATE Latin1_General_100_BIN2
            NOT LIKE N'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            OR TRY_CONVERT(date,@day,23) IS NULL
            OR CONVERT(nvarchar(10),TRY_CONVERT(date,@day,23),23) COLLATE Latin1_General_100_BIN2<>@day COLLATE Latin1_General_100_BIN2 RETURN NULL;
        IF @kind=N'date' AND DATALENGTH(@value)=20 RETURN @value;
        IF @kind=N'instant'
        BEGIN
            DECLARE @length int=DATALENGTH(@value)/2;
            IF @length<20 OR @length>32 RETURN NULL;
            IF SUBSTRING(@value,11,9) COLLATE Latin1_General_100_BIN2
               NOT LIKE N'T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]' RETURN NULL;
            IF TRY_CONVERT(int,SUBSTRING(@value,12,2))>23 RETURN NULL;
            DECLARE @zone_length int;
            IF RIGHT(@value,1) COLLATE Latin1_General_100_BIN2=N'Z' SET @zone_length=1;
            ELSE IF RIGHT(@value,6) COLLATE Latin1_General_100_BIN2 LIKE N'[-+][0-1][0-9]:[0-5][0-9]' SET @zone_length=6;
            ELSE RETURN NULL;
            IF @length<19+@zone_length RETURN NULL;
            DECLARE @fraction nvarchar(32)=SUBSTRING(@value,20,@length-19-@zone_length);
            IF @fraction<>N'' AND (LEFT(@fraction,1)<>N'.' OR LEN(@fraction)<2 OR LEN(@fraction)>7
               OR SUBSTRING(@fraction,2,32) COLLATE Latin1_General_100_BIN2 LIKE N'%[^0-9]%') RETURN NULL;
            IF TRY_CONVERT(datetimeoffset(6),@value,127) IS NOT NULL RETURN @value;
        END;
    END;
    RETURN NULL;
END;
GO

CREATE OR ALTER VIEW analytics.saved_analyses AS
SELECT a.case_id, a.analysis_id, a.runtime_mode, a.analysis_started_at,
       a.retrieval_window_ends_at, a.created_at AS analysis_created_at,
       a.material_hash, a.payload_json,
       TRY_CONVERT(datetimeoffset(6), analytics.report_scalar(material.value,
           N'scenario_effective_time',N'instant'),127) AS scenario_effective_time,
       JSON_VALUE(a.payload_json, '$.material.calculation_version') AS calculation_version,
       CASE WHEN identity_ok.ok=1 THEN JSON_VALUE(a.payload_json, '$.ranking.recommended_option_id') END AS recommended_option_id,
       CASE WHEN identity_ok.ok=1 THEN N'available' ELSE N'unavailable' END AS payload_state,
       CASE WHEN identity_ok.ok=1 AND valid.ok=1 THEN N'available' ELSE N'unavailable' END AS snapshot_state,
       CASE WHEN identity_ok.ok=1 AND valid.ok=1 THEN safe.snapshot_json END AS snapshot_json
FROM app.analysis_versions a
LEFT JOIN app.case_instances c ON c.case_id=a.case_id
OUTER APPLY (SELECT JSON_QUERY(a.payload_json,N'$.material') AS value) material
OUTER APPLY (SELECT COUNT(*) AS root_count, MAX(snapshot_json) AS snapshot_json
    FROM OPENJSON(CASE WHEN ISJSON(a.payload_json)=1
        AND LEFT(LTRIM(a.payload_json),1)=N'{' THEN a.payload_json ELSE N'{}' END)
    WITH (snapshot_json nvarchar(max) '$.material.operational_snapshot_json')) extracted
OUTER APPLY (SELECT CASE WHEN ISJSON(extracted.snapshot_json)=1
    AND extracted.root_count=1
    AND LEFT(LTRIM(extracted.snapshot_json),1)=N'{'
    THEN extracted.snapshot_json ELSE N'{}' END AS snapshot_json) safe
OUTER APPLY (SELECT CASE WHEN
    analytics.report_scalar(a.payload_json,N'case_id',N'text') COLLATE Latin1_General_100_BIN2=a.case_id COLLATE Latin1_General_100_BIN2
    AND analytics.report_scalar(a.payload_json,N'analysis_id',N'text') COLLATE Latin1_General_100_BIN2=a.analysis_id COLLATE Latin1_General_100_BIN2
    AND analytics.report_scalar(material.value,N'case_id',N'text') COLLATE Latin1_General_100_BIN2=a.case_id COLLATE Latin1_General_100_BIN2
    AND analytics.report_scalar(material.value,N'runtime_mode',N'text') COLLATE Latin1_General_100_BIN2=a.runtime_mode COLLATE Latin1_General_100_BIN2
    AND c.runtime_mode COLLATE Latin1_General_100_BIN2=a.runtime_mode COLLATE Latin1_General_100_BIN2
    AND a.runtime_mode COLLATE Latin1_General_100_BIN2 IN ('live','fallback')
    AND c.template_id COLLATE Latin1_General_100_BIN2=N'RL-001'
    AND analytics.report_scalar(material.value,N'template_id',N'text') COLLATE Latin1_General_100_BIN2=c.template_id COLLATE Latin1_General_100_BIN2
    AND analytics.report_scalar(material.value,N'corpus',N'text') COLLATE Latin1_General_100_BIN2=N'demo_corpus'
    AND TRY_CONVERT(datetimeoffset(6),analytics.report_scalar(material.value,N'scenario_effective_time',N'instant'),127)=c.scenario_effective_time
    THEN 1 ELSE 0 END AS ok) identity_ok
OUTER APPLY (SELECT CASE WHEN
    analytics.report_scalar(safe.snapshot_json,N'case_id',N'text') COLLATE Latin1_General_100_BIN2=a.case_id COLLATE Latin1_General_100_BIN2
    AND analytics.report_scalar(safe.snapshot_json,N'runtime_mode',N'text') COLLATE Latin1_General_100_BIN2=a.runtime_mode COLLATE Latin1_General_100_BIN2
    AND analytics.report_scalar(safe.snapshot_json,N'scenario_timezone',N'text') COLLATE Latin1_General_100_BIN2=N'America/Chicago'
    AND TRY_CONVERT(datetimeoffset(6),analytics.report_scalar(safe.snapshot_json,N'scenario_effective_time',N'instant'),127)=c.scenario_effective_time
    AND analytics.report_scalar(safe.snapshot_json,N'analysis_horizon_start',N'instant') IS NOT NULL
    AND analytics.report_scalar(safe.snapshot_json,N'analysis_horizon_end',N'date') IS NOT NULL
    AND LEFT(LTRIM(JSON_QUERY(safe.snapshot_json,N'$.inventory_positions')),1)=N'['
    AND LEFT(LTRIM(JSON_QUERY(safe.snapshot_json,N'$.production_orders')),1)=N'['
    AND LEFT(LTRIM(JSON_QUERY(safe.snapshot_json,N'$.customer_orders')),1)=N'['
    AND LEFT(LTRIM(JSON_QUERY(safe.snapshot_json,N'$.disruption')),1)=N'{'
    THEN 1 ELSE 0 END AS ok) valid;
GO

CREATE OR ALTER VIEW analytics.saved_options AS
WITH options AS (
    SELECT a.case_id,a.analysis_id,a.recommended_option_id,
           CASE WHEN j.[type]=5 THEN j.[value] ELSE N'{}' END AS option_json,
           analytics.report_scalar(j.[value],N'option_id',N'text') COLLATE Latin1_General_100_BIN2 AS option_id,
           COUNT(*) OVER (PARTITION BY a.case_id,a.analysis_id,
               analytics.report_scalar(j.[value],N'option_id',N'text') COLLATE Latin1_General_100_BIN2) AS identity_count
    FROM analytics.saved_analyses a
    CROSS APPLY (SELECT JSON_QUERY(a.payload_json,N'$.response_options') AS value) array_json
    CROSS APPLY OPENJSON(CASE WHEN LEFT(LTRIM(array_json.value),1)=N'[' THEN array_json.value ELSE N'[]' END) j
    WHERE j.[type]=5 AND a.payload_state=N'available'
)
SELECT case_id,analysis_id,option_id,
       JSON_VALUE(option_json,'$.option_kind') AS option_kind,
       JSON_VALUE(option_json,'$.name') AS option_name,
       CAST(CASE WHEN JSON_VALUE(option_json,'$.option_kind') COLLATE Latin1_General_100_BIN2='no_mitigation' THEN 1 ELSE 0 END AS bit) AS is_baseline,
       CAST(CASE WHEN option_id=recommended_option_id COLLATE Latin1_General_100_BIN2 THEN 1 ELSE 0 END AS bit) AS is_recommended,
       CASE analytics.report_scalar(option_json,N'executable',N'flag') WHEN 'true' THEN CAST(1 AS bit) WHEN 'false' THEN CAST(0 AS bit) END AS executable,
       CASE analytics.report_scalar(option_json,N'active_mitigation',N'flag') WHEN 'true' THEN CAST(1 AS bit) WHEN 'false' THEN CAST(0 AS bit) END AS active_mitigation,
       TRY_CONVERT(int,analytics.report_scalar(JSON_QUERY(option_json,'$.predicted'),N'uncovered_part_demand',N'integer')) AS uncovered_part_demand,
       CASE WHEN TRY_CONVERT(int,analytics.report_scalar(JSON_QUERY(option_json,'$.predicted'),N'otif_loss_percentage',N'integer'))<=100
         THEN TRY_CONVERT(int,analytics.report_scalar(JSON_QUERY(option_json,'$.predicted'),N'otif_loss_percentage',N'integer')) END AS otif_loss_percentage,
       TRY_CONVERT(decimal(19,4),analytics.report_scalar(JSON_QUERY(option_json,'$.predicted'),N'revenue_at_risk',N'money')) AS revenue_at_risk,
       TRY_CONVERT(decimal(19,4),analytics.report_scalar(JSON_QUERY(option_json,'$.predicted'),N'margin_at_risk',N'money')) AS margin_at_risk,
       TRY_CONVERT(decimal(19,4),analytics.report_scalar(JSON_QUERY(option_json,'$.predicted'),N'response_cost',N'money')) AS response_cost,
       JSON_QUERY(option_json,'$.predicted.protected_customer_order_ids') AS protected_customer_order_ids_json,
       JSON_QUERY(option_json,'$.assumptions') AS assumptions_json,
       JSON_QUERY(option_json,'$.blocking_codes') AS blocking_codes_json,
       JSON_QUERY(option_json,'$.prerequisite_roles') AS prerequisite_roles_json,
       JSON_QUERY(option_json,'$.evidence_ids') AS evidence_ids_json
FROM options WHERE identity_count=1 AND NULLIF(option_id,N'') IS NOT NULL;
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

IF OBJECT_ID(N'app.analysis_projection', N'V') IS NULL
    OR OBJECT_ID(N'app.decision_projection', N'V') IS NULL
    OR OBJECT_ID(N'analytics.case_command_center', N'V') IS NULL
    OR OBJECT_ID(N'analytics.action_outcomes', N'V') IS NULL
    THROW 51000, 'Required analytics views are missing.', 1;

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
