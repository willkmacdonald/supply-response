SELECT o.case_id,o.analysis_id,o.option_id,o.option_kind,o.option_name,
 CASE
   WHEN DATALENGTH(o.option_kind)=DATALENGTH(N'no_mitigation') AND o.option_kind COLLATE Latin1_General_100_BIN2=N'no_mitigation' THEN N'Do nothing — baseline'
   WHEN DATALENGTH(o.option_kind)=DATALENGTH(N'expedite') AND o.option_kind COLLATE Latin1_General_100_BIN2=N'expedite' THEN N'Expedite the partial shipment'
   WHEN DATALENGTH(o.option_kind)=DATALENGTH(N'transfer') AND o.option_kind COLLATE Latin1_General_100_BIN2=N'transfer' THEN N'Transfer from another plant'
   WHEN DATALENGTH(o.option_kind)=DATALENGTH(N'resequence') AND o.option_kind COLLATE Latin1_General_100_BIN2=N'resequence' THEN N'Prioritize production for customer needs'
   WHEN DATALENGTH(o.option_kind)=DATALENGTH(N'alternate_source') AND o.option_kind COLLATE Latin1_General_100_BIN2=N'alternate_source' THEN N'Use the alternate supplier'
   WHEN DATALENGTH(o.option_kind)=DATALENGTH(N'combined') AND o.option_kind COLLATE Latin1_General_100_BIN2=N'combined' THEN N'Combined response'
   ELSE N'Response option not recognized' END AS option_display_name,
 o.is_baseline,o.is_recommended,o.executable,o.active_mitigation,
 o.uncovered_part_demand,o.otif_loss_percentage,o.revenue_at_risk,
 o.margin_at_risk,o.response_cost,
 lists.blockers_text,lists.required_roles_text,lists.assumptions_text,
 lists.blocking_codes_text,lists.prerequisite_roles_text,
 lists.protected_customer_order_count,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),o.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),o.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),o.option_id)),2) AS option_key
FROM analytics.saved_options o
OUTER APPLY (
 SELECT
   MAX(CASE WHEN v.list_kind=N'blockers' THEN validated.display_text END) AS blockers_text,
   MAX(CASE WHEN v.list_kind=N'roles' THEN validated.display_text END) AS required_roles_text,
   MAX(CASE WHEN v.list_kind=N'assumptions' THEN validated.display_text END) AS assumptions_text,
   MAX(CASE WHEN v.list_kind=N'blockers' THEN validated.raw_text END) AS blocking_codes_text,
   MAX(CASE WHEN v.list_kind=N'roles' THEN validated.raw_text END) AS prerequisite_roles_text,
   MAX(CASE WHEN v.list_kind=N'protected' THEN validated.item_count END) AS protected_customer_order_count
 FROM (VALUES
   (N'blockers',o.blocking_codes_json),
   (N'roles',o.prerequisite_roles_json),
   (N'assumptions',o.assumptions_json),
   (N'protected',o.protected_customer_order_ids_json)
 ) v(list_kind,json_text)
 CROSS APPLY (SELECT CASE WHEN ISJSON(v.json_text)=1
   AND LEFT(LTRIM(v.json_text),1)=N'[' THEN 1 ELSE 0 END AS is_array) shape
 CROSS APPLY (
   SELECT COUNT(*) AS item_count,
     COUNT(DISTINCT CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),j.[value])),2)) AS distinct_count,
     COALESCE(SUM(CASE WHEN j.[type]=1 AND LEN(LTRIM(RTRIM(j.[value])))>0
       THEN 0 ELSE 1 END),0) AS invalid_count,
     STRING_AGG(mapped.display_value,NCHAR(10))
       WITHIN GROUP (ORDER BY CONVERT(int,j.[key])) AS joined_text
   FROM OPENJSON(CASE WHEN shape.is_array=1 THEN v.json_text ELSE N'[]' END) j
   CROSS APPLY (SELECT CONVERT(nvarchar(max),CASE
       WHEN v.list_kind=N'blockers' THEN CASE j.[value] COLLATE Latin1_General_100_BIN2
         WHEN N'QUALITY_QUALIFICATION_PENDING' THEN N'Cannot use Supplier Beta yet: supplier qualification is incomplete'
         WHEN N'ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE' THEN N'No partial shipment from Supplier Alpha is available'
         WHEN N'TRANSFER_INVENTORY_UNAVAILABLE' THEN N'The source plant does not have enough available inventory for this transfer'
         WHEN N'RESEQUENCE_NOT_APPLICABLE' THEN N'Changing the production sequence does not provide a response for this plan'
         ELSE N'Planning requirement not recognized — see Source details' END
       WHEN v.list_kind=N'roles' THEN CASE j.[value] COLLATE Latin1_General_100_BIN2
         WHEN N'material_planner' THEN N'Material planner'
         WHEN N'finance_approver' THEN N'Finance approver'
         WHEN N'quality_approver' THEN N'Quality approver'
         WHEN N'response_approver' THEN N'Response approver'
         ELSE N'Required role not recognized — see Source details' END
       ELSE j.[value]
     END) AS display_value) mapped
 ) parsed
 -- Keep raw and display ordered aggregates in separate scopes: combining them
 -- here triggers SQL Server error 8711 even with matching JSON-key expressions.
 CROSS APPLY (
   SELECT STRING_AGG(CONVERT(nvarchar(max),j.[value]),NCHAR(10))
     WITHIN GROUP (ORDER BY CONVERT(int,j.[key])) AS joined_raw_text
   FROM OPENJSON(CASE WHEN shape.is_array=1 THEN v.json_text ELSE N'[]' END) j
 ) raw_parsed
 CROSS APPLY (SELECT
   CASE WHEN shape.is_array=1 AND parsed.invalid_count=0
     AND (v.list_kind<>N'protected' OR parsed.item_count=parsed.distinct_count)
     THEN CASE WHEN parsed.item_count=0 THEN
       CASE v.list_kind
         WHEN N'blockers' THEN N'No planning blockers recorded'
         WHEN N'roles' THEN N'No required roles recorded'
         WHEN N'assumptions' THEN N'No assumptions recorded'
         ELSE N'No protected customer orders recorded' END
       ELSE parsed.joined_text END END AS display_text,
   CASE WHEN shape.is_array=1 AND parsed.invalid_count=0
     AND (v.list_kind<>N'protected' OR parsed.item_count=parsed.distinct_count)
     THEN CASE WHEN parsed.item_count=0 THEN
       CASE v.list_kind
         WHEN N'blockers' THEN N'No blocking codes recorded'
         WHEN N'roles' THEN N'No prerequisite role codes recorded'
         ELSE NULL END
       ELSE raw_parsed.joined_raw_text END END AS raw_text,
   CASE WHEN shape.is_array=1 AND parsed.invalid_count=0
     AND (v.list_kind<>N'protected' OR parsed.item_count=parsed.distinct_count)
     THEN parsed.item_count END AS item_count
 ) validated
) lists
