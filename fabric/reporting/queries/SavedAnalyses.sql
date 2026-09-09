SELECT a.case_id,a.analysis_id,a.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_started_at,'+00:00')) AS analysis_started_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.retrieval_window_ends_at,'+00:00')) AS retrieval_window_ends_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_created_at,'+00:00')) AS analysis_created_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 a.calculation_version,a.recommended_option_id,a.no_feasible_mitigation,a.payload_state,a.snapshot_state,
 completeness.inventory_complete,completeness.production_orders_complete,completeness.customer_orders_complete,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.recommended_option_id)),2) AS recommended_option_key
FROM analytics.saved_analyses a
OUTER APPLY (
 SELECT CAST(MAX(CASE WHEN f.family=N'inventory' THEN verdict.complete END) AS bit) AS inventory_complete,
        CAST(MAX(CASE WHEN f.family=N'production_order' THEN verdict.complete END) AS bit) AS production_orders_complete,
        CAST(MAX(CASE WHEN f.family=N'customer_order_line' THEN verdict.complete END) AS bit) AS customer_orders_complete
 FROM (VALUES (N'inventory_positions',N'inventory'),
              (N'production_orders',N'production_order'),
              (N'customer_orders',N'customer_order_line')) f(property_name,family)
 CROSS APPLY (
   SELECT COUNT(*) AS property_count,MAX(j.[type]) AS property_type,MAX(j.[value]) AS array_json
   FROM OPENJSON(CASE WHEN ISJSON(a.snapshot_json)=1 AND LEFT(LTRIM(a.snapshot_json),1)=N'{'
                     THEN a.snapshot_json ELSE N'{}' END) j
   WHERE j.[key] COLLATE Latin1_General_100_BIN2=f.property_name COLLATE Latin1_General_100_BIN2
 ) property
 CROSS APPLY (
   SELECT COUNT(*) AS raw_count,COALESCE(SUM(CASE WHEN j.[type]=5 THEN 0 ELSE 1 END),0) AS nonobject_count
   FROM OPENJSON(CASE WHEN property.property_count=1 AND property.property_type=4
                     THEN property.array_json ELSE N'[]' END) j
 ) raw_members
 CROSS APPLY (
   SELECT COUNT(*) AS projected_count,
          COALESCE(SUM(CASE WHEN r.record_state=N'available' THEN 0 ELSE 1 END),0) AS unavailable_count
   FROM analytics.saved_records r
   WHERE r.case_id COLLATE Latin1_General_100_BIN2=a.case_id COLLATE Latin1_General_100_BIN2
     AND r.analysis_id COLLATE Latin1_General_100_BIN2=a.analysis_id COLLATE Latin1_General_100_BIN2
     AND r.record_family COLLATE Latin1_General_100_BIN2=f.family COLLATE Latin1_General_100_BIN2
 ) projected
 CROSS APPLY (SELECT CASE WHEN a.snapshot_state=N'available' AND a.payload_state=N'available'
    AND property.property_count=1 AND property.property_type=4
    AND raw_members.nonobject_count=0 AND raw_members.raw_count=projected.projected_count
    AND projected.unavailable_count=0 THEN 1 ELSE 0 END AS complete) verdict
) completeness
