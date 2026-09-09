SELECT r.case_id,r.analysis_id,r.record_family,r.source_record_id,r.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(r.analysis_created_at,'+00:00')) AS analysis_created_at,
 CONVERT(datetime2(6),SWITCHOFFSET(r.scenario_effective_time,'+00:00')) AS scenario_effective_time,r.record_state,
 r.supplier_id,r.part_id,r.plant_id,r.source_plant_id,r.destination_plant_id,
 r.product_id,r.customer_id,r.production_order_id,r.customer_order_id,r.po_line_id,
 r.quantity,r.due_date,r.dispatch_date,r.arrival_date,r.incremental_cost_per_unit,
 r.status,r.evidence_ref,r.audit_complete,r.first_article_complete,
 r.effective_date,r.expected_decision_date,r.on_hand,r.quality_hold,
 r.protected_allocation,r.usable_inventory,r.component_demand,r.customer_priority,
 r.customer_revenue,r.customer_margin,r.unit_revenue,r.unit_margin,r.line_revenue,
 r.original_quantity,r.partial_quantity,r.original_due_date,r.partial_due_date,
 r.recovery_date,r.source_ref,
 e.evidence_state,e.provenance,e.evidence_id,e.source_id,e.source_system,
 e.synthetic,
 CONVERT(datetime2(6),SWITCHOFFSET(e.source_timestamp,'+00:00')) AS source_timestamp,
 CONVERT(datetime2(6),SWITCHOFFSET(e.retrieved_at,'+00:00')) AS retrieved_at,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.source_record_id)),2) AS record_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.part_id)),2) AS part_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.plant_id)),2) AS plant_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.product_id)),2) AS product_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.source_plant_id)),2) AS source_plant_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.destination_plant_id)),2) AS destination_plant_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),r.production_order_id)),2) AS production_order_key,
 CAST(CASE WHEN r.record_state=N'available' AND d.disruption_count=1
   AND d.disruption_state=N'available' THEN
   CASE
     WHEN r.record_family=N'inventory'
       AND r.part_id COLLATE Latin1_General_100_BIN2=d.part_id COLLATE Latin1_General_100_BIN2
       AND r.plant_id COLLATE Latin1_General_100_BIN2=d.plant_id COLLATE Latin1_General_100_BIN2 THEN 1
     WHEN r.record_family=N'production_order' THEN 1
     WHEN r.record_family=N'customer_order_line' AND EXISTS (
       SELECT 1 FROM analytics.saved_records p
       WHERE p.case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
         AND p.analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
         AND p.record_family=N'production_order' AND p.record_state=N'available'
         AND p.source_record_id COLLATE Latin1_General_100_BIN2=r.production_order_id COLLATE Latin1_General_100_BIN2
     ) THEN 1
     ELSE 0
   END ELSE 0 END AS bit) AS in_disruption_scope
FROM analytics.saved_records r
LEFT JOIN analytics.saved_record_evidence e
 ON e.case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
 AND e.analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
 AND e.record_family COLLATE Latin1_General_100_BIN2=r.record_family COLLATE Latin1_General_100_BIN2
 AND e.source_record_id COLLATE Latin1_General_100_BIN2=r.source_record_id COLLATE Latin1_General_100_BIN2
OUTER APPLY (
 SELECT COUNT(*) AS disruption_count,MAX(x.record_state) AS disruption_state,
   MAX(x.part_id) AS part_id,MAX(x.plant_id) AS plant_id
 FROM analytics.saved_records x
 WHERE x.case_id COLLATE Latin1_General_100_BIN2=r.case_id COLLATE Latin1_General_100_BIN2
   AND x.analysis_id COLLATE Latin1_General_100_BIN2=r.analysis_id COLLATE Latin1_General_100_BIN2
   AND x.record_family=N'disruption'
) d
