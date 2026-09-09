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

CREATE OR ALTER VIEW analytics.saved_records AS
WITH candidates AS (
    SELECT a.case_id,a.analysis_id,a.runtime_mode,a.analysis_created_at,
           a.scenario_effective_time,f.record_family,j.[value] AS record_json,
           analytics.report_scalar(j.[value],SUBSTRING(f.id_path,3,128),N'text') COLLATE Latin1_General_100_BIN2 AS source_record_id
    FROM analytics.saved_analyses a
    CROSS APPLY (VALUES
       (N'disruption',N'$.disruption',N'$.disruption_id',0),
       (N'shipment',N'$.alpha_expedite',N'$.receipt_id',0),
       (N'transfer',N'$.transfer',N'$.transfer_id',0),
       (N'qualification',N'$.beta_qualification',N'$.qualification_id',0),
       (N'inventory',N'$.inventory_positions',N'$.inventory_id',1),
       (N'production_order',N'$.production_orders',N'$.production_order_id',1),
       (N'customer_order_line',N'$.customer_orders',N'$.customer_order_line_id',1)
    ) f(record_family,json_path,id_path,is_array)
    CROSS APPLY (SELECT JSON_QUERY(COALESCE(a.snapshot_json,N'{}'),f.json_path) AS value) raw
    CROSS APPLY OPENJSON(CASE
       WHEN f.is_array=1 AND LEFT(LTRIM(raw.value),1)=N'[' THEN raw.value
       WHEN f.is_array=0 AND LEFT(LTRIM(raw.value),1)=N'{' THEN N'['+raw.value+N']'
       ELSE N'[]' END) j
    WHERE j.[type]=5
), unique_records AS (
    SELECT *,COUNT(*) OVER (PARTITION BY case_id,analysis_id,record_family,source_record_id) AS identity_count
    FROM candidates
)
SELECT r.case_id,r.analysis_id,r.record_family,r.source_record_id,r.runtime_mode,
       r.analysis_created_at,r.scenario_effective_time,
       CASE WHEN
         (r.record_family='shipment' AND x.supplier_id IS NOT NULL AND x.part_id IS NOT NULL
          AND x.plant_id IS NOT NULL AND TRY_CONVERT(int,x.quantity)>0
          AND TRY_CONVERT(date,x.due_date,23) IS NOT NULL AND TRY_CONVERT(decimal(19,4),x.incremental_cost_per_unit)>=0)
         OR (r.record_family='transfer' AND x.part_id IS NOT NULL AND x.source_plant_id IS NOT NULL
          AND x.destination_plant_id IS NOT NULL AND TRY_CONVERT(int,x.quantity)>0
          AND TRY_CONVERT(date,x.dispatch_date,23) IS NOT NULL AND TRY_CONVERT(date,x.arrival_date,23) IS NOT NULL
          AND TRY_CONVERT(decimal(19,4),x.incremental_cost_per_unit)>=0)
         OR (r.record_family='qualification' AND x.supplier_id IS NOT NULL AND x.part_id IS NOT NULL
          AND x.evidence_ref IS NOT NULL AND x.status COLLATE Latin1_General_100_BIN2 IN ('approved','pending','not_approved','conditional')
          AND x.audit_complete IN ('#null','true','false')
          AND x.first_article_complete IN ('#null','true','false')
          AND (x.effective_date='#null' OR TRY_CONVERT(date,x.effective_date,23) IS NOT NULL)
          AND (x.expected_decision_date='#null' OR TRY_CONVERT(date,x.expected_decision_date,23) IS NOT NULL))
         OR (r.record_family='inventory' AND x.part_id IS NOT NULL AND x.plant_id IS NOT NULL
          AND TRY_CONVERT(int,x.on_hand)>=0 AND TRY_CONVERT(int,x.quality_hold)>=0
          AND TRY_CONVERT(int,x.protected_allocation)>=0)
         OR (r.record_family IN ('production_order','customer_order_line')
          AND x.product_id IS NOT NULL AND x.plant_id IS NOT NULL
          AND TRY_CONVERT(int,x.quantity)>0 AND TRY_CONVERT(date,x.due_date,23) IS NOT NULL)
         OR (r.record_family='disruption' AND x.supplier_id IS NOT NULL AND x.part_id IS NOT NULL
          AND x.plant_id IS NOT NULL AND x.po_line_id IS NOT NULL AND x.source_ref IS NOT NULL
          AND TRY_CONVERT(int,x.original_quantity)>0 AND TRY_CONVERT(int,x.partial_quantity)>=0
          AND TRY_CONVERT(date,x.original_due_date,23) IS NOT NULL)
         THEN N'available' ELSE N'unavailable' END AS record_state,
       x.supplier_id,x.part_id,x.plant_id,x.source_plant_id,x.destination_plant_id,
       x.product_id,x.customer_id,x.production_order_id,x.customer_order_id,x.po_line_id,
       TRY_CONVERT(int,x.quantity) AS quantity,
       TRY_CONVERT(date,x.due_date,23) AS due_date,
       TRY_CONVERT(date,x.dispatch_date,23) AS dispatch_date,
       TRY_CONVERT(date,x.arrival_date,23) AS arrival_date,
       TRY_CONVERT(decimal(19,4),x.incremental_cost_per_unit) AS incremental_cost_per_unit,
       x.status,x.evidence_ref,
       CASE x.audit_complete WHEN 'true' THEN CAST(1 AS bit) WHEN 'false' THEN CAST(0 AS bit) END AS audit_complete,
       CASE x.first_article_complete WHEN 'true' THEN CAST(1 AS bit) WHEN 'false' THEN CAST(0 AS bit) END AS first_article_complete,
       TRY_CONVERT(date,x.effective_date,23) AS effective_date,
       TRY_CONVERT(date,x.expected_decision_date,23) AS expected_decision_date,
       TRY_CONVERT(int,x.on_hand) AS on_hand,
       TRY_CONVERT(int,x.quality_hold) AS quality_hold,
       TRY_CONVERT(int,x.protected_allocation) AS protected_allocation,
       TRY_CONVERT(bigint,x.on_hand)-TRY_CONVERT(bigint,x.quality_hold)-TRY_CONVERT(bigint,x.protected_allocation) AS usable_inventory,
       TRY_CONVERT(int,x.component_demand) AS component_demand,
       TRY_CONVERT(int,x.customer_priority) AS customer_priority,
       TRY_CONVERT(decimal(19,4),x.customer_revenue) AS customer_revenue,
       TRY_CONVERT(decimal(19,4),x.customer_margin) AS customer_margin,
       TRY_CONVERT(decimal(19,4),x.unit_revenue) AS unit_revenue,
       TRY_CONVERT(decimal(19,4),x.unit_margin) AS unit_margin,
       TRY_CONVERT(int,x.quantity)*TRY_CONVERT(decimal(19,4),x.unit_revenue) AS line_revenue,
       TRY_CONVERT(int,x.original_quantity) AS original_quantity,
       TRY_CONVERT(int,x.partial_quantity) AS partial_quantity,
       TRY_CONVERT(date,x.original_due_date,23) AS original_due_date,
       TRY_CONVERT(date,x.partial_due_date,23) AS partial_due_date,
       TRY_CONVERT(date,x.recovery_date,23) AS recovery_date,
       x.source_ref
FROM unique_records r
CROSS APPLY (SELECT
    analytics.report_scalar(r.record_json,N'supplier_id',N'text') AS supplier_id,
    analytics.report_scalar(r.record_json,N'part_id',N'text') AS part_id,
    analytics.report_scalar(r.record_json,N'plant_id',N'text') AS plant_id,
    analytics.report_scalar(r.record_json,N'source_plant_id',N'text') AS source_plant_id,
    analytics.report_scalar(r.record_json,N'destination_plant_id',N'text') AS destination_plant_id,
    analytics.report_scalar(r.record_json,N'product_id',N'text') AS product_id,
    analytics.report_scalar(r.record_json,N'customer_id',N'text') AS customer_id,
    analytics.report_scalar(r.record_json,N'production_order_id',N'text') AS production_order_id,
    analytics.report_scalar(r.record_json,N'customer_order_id',N'text') AS customer_order_id,
    analytics.report_scalar(r.record_json,N'po_line_id',N'text') AS po_line_id,
    analytics.report_scalar(r.record_json,N'quantity',N'integer') AS quantity,
    analytics.report_scalar(r.record_json,N'due_date',N'date') AS due_date,
    analytics.report_scalar(r.record_json,N'dispatch_date',N'date') AS dispatch_date,
    analytics.report_scalar(r.record_json,N'arrival_date',N'date') AS arrival_date,
    analytics.report_scalar(r.record_json,N'incremental_cost_per_unit',N'money') AS incremental_cost_per_unit,
    analytics.report_scalar(r.record_json,N'status',N'text') AS status,
    analytics.report_scalar(r.record_json,N'evidence_ref',N'text') AS evidence_ref,
    analytics.report_scalar(r.record_json,N'audit_complete',N'nullable_flag') AS audit_complete,
    analytics.report_scalar(r.record_json,N'first_article_complete',N'nullable_flag') AS first_article_complete,
    analytics.report_scalar(r.record_json,N'effective_date',N'nullable_date') AS effective_date,
    analytics.report_scalar(r.record_json,N'expected_decision_date',N'nullable_date') AS expected_decision_date,
    analytics.report_scalar(r.record_json,N'on_hand',N'integer') AS on_hand,
    analytics.report_scalar(r.record_json,N'quality_hold',N'integer') AS quality_hold,
    analytics.report_scalar(r.record_json,N'protected_allocation',N'integer') AS protected_allocation,
    analytics.report_scalar(r.record_json,N'component_demand',N'integer') AS component_demand,
    analytics.report_scalar(r.record_json,N'customer_priority',N'integer') AS customer_priority,
    analytics.report_scalar(r.record_json,N'customer_revenue',N'money') AS customer_revenue,
    analytics.report_scalar(r.record_json,N'customer_margin',N'money') AS customer_margin,
    analytics.report_scalar(r.record_json,N'unit_revenue',N'money') AS unit_revenue,
    analytics.report_scalar(r.record_json,N'unit_margin',N'money') AS unit_margin,
    analytics.report_scalar(r.record_json,N'original_quantity',N'integer') AS original_quantity,
    analytics.report_scalar(r.record_json,N'partial_quantity',N'integer') AS partial_quantity,
    analytics.report_scalar(r.record_json,N'original_due_date',N'date') AS original_due_date,
    analytics.report_scalar(r.record_json,N'partial_due_date',N'nullable_date') AS partial_due_date,
    analytics.report_scalar(r.record_json,N'recovery_date',N'nullable_date') AS recovery_date,
    analytics.report_scalar(r.record_json,N'source_ref',N'text') AS source_ref
) x
WHERE r.identity_count=1 AND NULLIF(r.source_record_id,N'') IS NOT NULL;
GO

CREATE OR ALTER VIEW analytics.saved_record_evidence AS
WITH raw_evidence AS (
    SELECT a.case_id,a.analysis_id,j.[value] AS evidence_json,
           analytics.report_scalar(j.[value],N'evidence_id',N'text') COLLATE Latin1_General_100_BIN2 AS evidence_id,
           analytics.report_scalar(j.[value],N'source_id',N'text') COLLATE Latin1_General_100_BIN2 AS source_id
    FROM analytics.saved_analyses a
    CROSS APPLY (SELECT JSON_QUERY(a.payload_json,N'$.evidence_items') AS value) array_json
    CROSS APPLY OPENJSON(CASE WHEN LEFT(LTRIM(array_json.value),1)=N'[' THEN array_json.value ELSE N'[]' END) j
    WHERE j.[type]=5 AND a.payload_state=N'available'
), evidence AS (
    SELECT *,COUNT(*) OVER (PARTITION BY case_id,analysis_id,evidence_id) AS evidence_id_count,
             COUNT(*) OVER (PARTITION BY case_id,analysis_id,source_id) AS source_id_count
    FROM raw_evidence
), raw_material AS (
    SELECT a.case_id,a.analysis_id,j.[value] AS material_json,
           analytics.report_scalar(j.[value],N'evidence_id',N'text') COLLATE Latin1_General_100_BIN2 AS evidence_id
    FROM analytics.saved_analyses a
    CROSS APPLY (SELECT JSON_QUERY(a.payload_json,N'$.material.evidence') AS value) array_json
    CROSS APPLY OPENJSON(CASE WHEN LEFT(LTRIM(array_json.value),1)=N'[' THEN array_json.value ELSE N'[]' END) j
    WHERE j.[type]=5
), material AS (
    SELECT *,COUNT(*) OVER (PARTITION BY case_id,analysis_id,evidence_id) AS material_id_count
    FROM raw_material
), expected AS (
    SELECT r.*,
      CASE WHEN r.record_family='qualification' THEN r.evidence_ref ELSE r.source_record_id END COLLATE Latin1_General_100_BIN2 AS expected_evidence_id,
      CASE WHEN r.runtime_mode='fallback' THEN N'RL-SOURCE-'+
           CASE WHEN r.record_family='qualification' THEN r.evidence_ref ELSE r.source_record_id END
           ELSE CASE r.record_family WHEN 'shipment' THEN N'fabric.supply_receipt/'
             WHEN 'transfer' THEN N'fabric.inventory_transfer/'
             WHEN 'qualification' THEN N'fabric.qualification/' END+r.source_record_id END COLLATE Latin1_General_100_BIN2 AS expected_source_id
    FROM analytics.saved_records r WHERE r.record_family IN ('shipment','transfer','qualification')
), records AS (
    SELECT *,COUNT(*) OVER (PARTITION BY case_id,analysis_id,expected_source_id) AS matching_record_count
    FROM expected
)
SELECT r.case_id,r.analysis_id,r.record_family,r.source_record_id,
       CASE WHEN valid.ok=1 THEN N'available' ELSE N'unavailable' END AS evidence_state,
       CASE WHEN valid.ok=1 THEN CASE WHEN r.runtime_mode='live' THEN N'saved_fabric' ELSE N'demo_fixture' END END AS provenance,
       CASE WHEN valid.ok=1 THEN e.evidence_id END AS evidence_id,
       CASE WHEN valid.ok=1 THEN e.source_id END AS source_id,
       CASE WHEN valid.ok=1 THEN f.source_system END AS source_system,
       CASE WHEN valid.ok=1 THEN CASE f.synthetic WHEN 'true' THEN CAST(1 AS bit) WHEN 'false' THEN CAST(0 AS bit) END END AS synthetic,
       CASE WHEN valid.ok=1 THEN TRY_CONVERT(datetimeoffset(6),NULLIF(f.source_timestamp,N'#null'),127) END AS source_timestamp,
       CASE WHEN valid.ok=1 THEN TRY_CONVERT(datetimeoffset(6),NULLIF(f.retrieved_at,N'#null'),127) END AS retrieved_at
FROM records r
LEFT JOIN evidence e ON e.case_id=r.case_id AND e.analysis_id=r.analysis_id
    AND e.evidence_id=r.expected_evidence_id AND e.evidence_id_count=1 AND e.source_id_count=1
LEFT JOIN material m ON m.case_id=r.case_id AND m.analysis_id=r.analysis_id
    AND m.evidence_id=r.expected_evidence_id AND m.material_id_count=1
OUTER APPLY (SELECT
    analytics.report_scalar(e.evidence_json,N'case_id',N'text') AS evidence_case_id,
    analytics.report_scalar(e.evidence_json,N'kind',N'text') AS kind,
    analytics.report_scalar(e.evidence_json,N'source_system',N'text') AS source_system,
    analytics.report_scalar(e.evidence_json,N'runtime_mode',N'text') AS runtime_mode,
    analytics.report_scalar(e.evidence_json,N'synthetic',N'flag') AS synthetic,
    analytics.report_scalar(e.evidence_json,N'source_timestamp',N'nullable_instant') AS source_timestamp,
    analytics.report_scalar(e.evidence_json,N'retrieved_at',N'nullable_instant') AS retrieved_at,
    analytics.report_scalar(e.evidence_json,N'retrieved_for_analysis_id',N'text') AS retrieved_for_analysis_id) f
OUTER APPLY (SELECT CASE WHEN r.record_state='available' AND r.matching_record_count=1
    AND e.evidence_id=m.evidence_id AND e.source_id=r.expected_source_id
    AND f.evidence_case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
    AND f.kind COLLATE Latin1_General_100_BIN2=N'operational_fact'
    AND f.runtime_mode COLLATE Latin1_General_100_BIN2=r.runtime_mode COLLATE Latin1_General_100_BIN2
    AND f.retrieved_for_analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
    AND f.retrieved_at IS NOT NULL
    AND ((r.runtime_mode='live' AND f.source_system COLLATE Latin1_General_100_BIN2=N'fabric' AND f.synthetic=N'false')
      OR (r.runtime_mode='fallback' AND f.source_system COLLATE Latin1_General_100_BIN2=N'synthetic_fixture' AND f.synthetic=N'true'))
    AND NOT EXISTS (
        SELECT 1 FROM (VALUES
          (N'case_id',N'text'),(N'kind',N'text'),(N'source_system',N'text'),
          (N'source_id',N'text'),(N'runtime_mode',N'text'),(N'synthetic',N'flag'),
          (N'source_timestamp',N'nullable_instant')
        ) identity_field(name,kind)
        WHERE analytics.report_scalar(e.evidence_json,identity_field.name,identity_field.kind) IS NULL
           OR analytics.report_scalar(m.material_json,identity_field.name,identity_field.kind) IS NULL
           OR analytics.report_scalar(e.evidence_json,identity_field.name,identity_field.kind) COLLATE Latin1_General_100_BIN2
              <>analytics.report_scalar(m.material_json,identity_field.name,identity_field.kind) COLLATE Latin1_General_100_BIN2
    ) THEN 1 ELSE 0 END AS ok) valid;
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

CREATE OR ALTER VIEW analytics.case_reporting AS
SELECT c.case_id,c.purpose,c.status,c.runtime_mode,c.scenario_effective_time,
       c.current_analysis_id,c.current_decision_id,a.analysis_created_at,a.snapshot_state,
       a.recommended_option_id,
       CASE WHEN base.baseline_count=1 THEN base.option_id END AS baseline_option_id,
       d.kind AS decision_kind,d.analysis_id AS decision_analysis_id,d.decided_at,
       CASE WHEN d.kind='approved' THEN d.selected_option_id END AS approved_option_id,
       b.revenue_at_risk AS baseline_revenue_at_risk,
       b.otif_loss_percentage AS baseline_otif_loss_percentage,
       b.uncovered_part_demand AS baseline_uncovered_part_demand,
       b.response_cost AS baseline_response_cost,
       r.revenue_at_risk AS recommended_revenue_at_risk,
       r.otif_loss_percentage AS recommended_otif_loss_percentage,
       r.uncovered_part_demand AS recommended_uncovered_part_demand,
       r.response_cost AS recommended_response_cost,
       approved.revenue_at_risk AS approved_revenue_at_risk,
       approved.otif_loss_percentage AS approved_otif_loss_percentage,
       approved.uncovered_part_demand AS approved_uncovered_part_demand,
       approved.response_cost AS approved_response_cost
FROM app.case_projection c
LEFT JOIN analytics.saved_analyses a ON a.case_id=c.case_id AND a.analysis_id=c.current_analysis_id
OUTER APPLY (SELECT COUNT(*) AS baseline_count,MIN(o.option_id) AS option_id
             FROM analytics.saved_options o WHERE o.case_id=c.case_id
             AND o.analysis_id=c.current_analysis_id AND o.is_baseline=1) base
LEFT JOIN analytics.saved_options b ON base.baseline_count=1 AND b.case_id=c.case_id
    AND b.analysis_id=c.current_analysis_id AND b.option_id=base.option_id
LEFT JOIN analytics.saved_options r ON r.case_id=c.case_id AND r.analysis_id=c.current_analysis_id
    AND r.option_id=a.recommended_option_id COLLATE Latin1_General_100_BIN2
LEFT JOIN app.decision_projection d ON d.case_id=c.case_id AND d.decision_id=c.current_decision_id
LEFT JOIN analytics.saved_options approved ON d.kind='approved' AND approved.case_id=c.case_id
    AND approved.analysis_id=d.analysis_id
    AND approved.option_id=d.selected_option_id COLLATE Latin1_General_100_BIN2;
GO

IF OBJECT_ID(N'app.analysis_projection', N'V') IS NULL
    OR OBJECT_ID(N'app.decision_projection', N'V') IS NULL
    OR OBJECT_ID(N'analytics.case_command_center', N'V') IS NULL
    OR OBJECT_ID(N'analytics.action_outcomes', N'V') IS NULL
    OR OBJECT_ID(N'analytics.report_scalar', N'FN') IS NULL
    OR OBJECT_ID(N'analytics.saved_analyses', N'V') IS NULL
    OR OBJECT_ID(N'analytics.saved_options', N'V') IS NULL
    OR OBJECT_ID(N'analytics.saved_records', N'V') IS NULL
    OR OBJECT_ID(N'analytics.saved_record_evidence', N'V') IS NULL
    OR OBJECT_ID(N'analytics.case_reporting', N'V') IS NULL
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
