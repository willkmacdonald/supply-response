IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'reporting')
    EXEC(N'CREATE SCHEMA reporting');
GO

IF OBJECT_ID(N'reporting.datasets', N'U') IS NULL
BEGIN
    CREATE TABLE reporting.datasets (
        dataset_id nvarchar(128) NOT NULL,
        effective_at datetimeoffset(6) NOT NULL,
        content_sha256 char(64) NOT NULL,
        is_synthetic bit NOT NULL,
        payload_json nvarchar(max) NOT NULL,
        CONSTRAINT PK_reporting_datasets PRIMARY KEY (dataset_id),
        CONSTRAINT CK_reporting_datasets_synthetic CHECK (is_synthetic = 1),
        CONSTRAINT CK_reporting_datasets_json CHECK (ISJSON(payload_json) = 1),
        CONSTRAINT CK_reporting_datasets_hash CHECK (
            content_sha256 NOT LIKE '%[^0-9a-f]%' AND LEN(content_sha256) = 64
        )
    );
END;
GO

CREATE OR ALTER VIEW reporting.operational_records AS
SELECT d.dataset_id,
       d.effective_at,
       r.record_id,
       r.record_family,
       r.supplier_id,
       r.supplier_name,
       r.part_id,
       r.part_name,
       r.plant_id,
       r.plant_name,
       r.source_plant_id,
       r.source_plant_name,
       r.destination_plant_id,
       r.destination_plant_name,
       r.customer_id,
       r.product_id,
       r.production_order_id,
       r.customer_order_id,
       r.quantity,
       r.on_hand,
       r.quality_hold,
       r.protected_allocation,
       r.usable_inventory,
       r.component_demand,
       r.due_date,
       r.original_due_date,
       r.dispatch_date,
       r.arrival_date,
       r.incremental_cost_per_unit,
       r.line_revenue,
       r.line_margin,
       r.status,
       r.audit_complete,
       r.first_article_complete,
       r.expected_decision_date,
       r.data_origin
FROM reporting.datasets d
CROSS APPLY OPENJSON(d.payload_json, '$.records') j
CROSS APPLY OPENJSON(j.[value])
WITH (
    record_id nvarchar(128) '$.record_id',
    record_family nvarchar(32) '$.record_family',
    supplier_id nvarchar(128) '$.supplier_id',
    supplier_name nvarchar(256) '$.supplier_name',
    part_id nvarchar(128) '$.part_id',
    part_name nvarchar(256) '$.part_name',
    plant_id nvarchar(128) '$.plant_id',
    plant_name nvarchar(256) '$.plant_name',
    source_plant_id nvarchar(128) '$.source_plant_id',
    source_plant_name nvarchar(256) '$.source_plant_name',
    destination_plant_id nvarchar(128) '$.destination_plant_id',
    destination_plant_name nvarchar(256) '$.destination_plant_name',
    customer_id nvarchar(128) '$.customer_id',
    product_id nvarchar(128) '$.product_id',
    production_order_id nvarchar(128) '$.production_order_id',
    customer_order_id nvarchar(128) '$.customer_order_id',
    quantity int '$.quantity',
    on_hand int '$.on_hand',
    quality_hold int '$.quality_hold',
    protected_allocation int '$.protected_allocation',
    usable_inventory int '$.usable_inventory',
    component_demand int '$.component_demand',
    due_date date '$.due_date',
    original_due_date date '$.original_due_date',
    dispatch_date date '$.dispatch_date',
    arrival_date date '$.arrival_date',
    incremental_cost_per_unit decimal(19,2) '$.incremental_cost_per_unit',
    line_revenue decimal(19,2) '$.line_revenue',
    line_margin decimal(19,2) '$.line_margin',
    status nvarchar(64) '$.status',
    audit_complete bit '$.audit_complete',
    first_article_complete bit '$.first_article_complete',
    expected_decision_date date '$.expected_decision_date',
    data_origin nvarchar(64) '$.data_origin'
) r
WHERE d.is_synthetic = 1
  AND JSON_VALUE(d.payload_json, '$.dataset_id') = d.dataset_id
  AND j.[type] = 5
  AND LEN(JSON_VALUE(j.[value], '$.record_id')) BETWEEN 1 AND 128
  AND r.record_family IN (N'inventory', N'purchase', N'shipment', N'transfer',
      N'qualification', N'production_order', N'customer_order')
  AND r.data_origin IN (N'canonical_scenario', N'fictional_reporting_context')
  AND (r.quantity IS NULL OR r.quantity >= 0)
  AND (r.on_hand IS NULL OR r.on_hand >= 0)
  AND (r.quality_hold IS NULL OR r.quality_hold >= 0)
  AND (r.protected_allocation IS NULL OR r.protected_allocation >= 0)
  AND (r.usable_inventory IS NULL OR r.usable_inventory >= 0)
  AND (r.component_demand IS NULL OR r.component_demand >= 0)
  AND (r.supplier_id IS NULL OR LEN(JSON_VALUE(j.[value], '$.supplier_id')) <= 128)
  AND (r.supplier_name IS NULL OR LEN(JSON_VALUE(j.[value], '$.supplier_name')) <= 256)
  AND (r.part_id IS NULL OR LEN(JSON_VALUE(j.[value], '$.part_id')) <= 128)
  AND (r.part_name IS NULL OR LEN(JSON_VALUE(j.[value], '$.part_name')) <= 256)
  AND (r.status IS NULL OR LEN(JSON_VALUE(j.[value], '$.status')) <= 64);
GO
