SELECT a.case_id,a.decision_id,a.selected_option_id,a.record_type,a.action_id,
 a.action_kind,
 CASE
   WHEN DATALENGTH(a.action_kind)=DATALENGTH(N'prepare_alpha_recovery_draft') AND a.action_kind COLLATE Latin1_General_100_BIN2=N'prepare_alpha_recovery_draft' THEN N'Prepare supplier recovery draft'
   WHEN DATALENGTH(a.action_kind)=DATALENGTH(N'coordinate_alpha_expedited_partial') AND a.action_kind COLLATE Latin1_General_100_BIN2=N'coordinate_alpha_expedited_partial' THEN N'Coordinate expedited partial shipment'
   WHEN DATALENGTH(a.action_kind)=DATALENGTH(N'transfer_dallas_to_chicago') AND a.action_kind COLLATE Latin1_General_100_BIN2=N'transfer_dallas_to_chicago' THEN N'Transfer stock from Dallas to Chicago'
   WHEN DATALENGTH(a.action_kind)=DATALENGTH(N'resequence_priority_production') AND a.action_kind COLLATE Latin1_General_100_BIN2=N'resequence_priority_production' THEN N'Prioritize production for customer needs'
   WHEN DATALENGTH(a.action_kind)=DATALENGTH(N'update_disruption_status') AND a.action_kind COLLATE Latin1_General_100_BIN2=N'update_disruption_status' THEN N'Update disruption status'
   ELSE N'Action type not recognized' END AS action_display_name,
 a.action_status,
 CASE
   WHEN DATALENGTH(a.action_status)=DATALENGTH(N'planned') AND a.action_status COLLATE Latin1_General_100_BIN2=N'planned' THEN N'Planned'
   WHEN DATALENGTH(a.action_status)=DATALENGTH(N'in_progress') AND a.action_status COLLATE Latin1_General_100_BIN2=N'in_progress' THEN N'In progress'
   WHEN DATALENGTH(a.action_status)=DATALENGTH(N'completed') AND a.action_status COLLATE Latin1_General_100_BIN2=N'completed' THEN N'Completed'
   WHEN DATALENGTH(a.action_status)=DATALENGTH(N'failed') AND a.action_status COLLATE Latin1_General_100_BIN2=N'failed' THEN N'Failed'
   ELSE N'Status not recognized' END AS action_status_display,
 a.metric,
 CASE
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'alpha_expedited_quantity') AND a.metric COLLATE Latin1_General_100_BIN2=N'alpha_expedited_quantity' THEN N'Supplier Alpha expedited quantity'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'dallas_transfer_quantity') AND a.metric COLLATE Latin1_General_100_BIN2=N'dallas_transfer_quantity' THEN N'Dallas transfer quantity'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'total_response_arranged_supply') AND a.metric COLLATE Latin1_General_100_BIN2=N'total_response_arranged_supply' THEN N'Total supply arranged by the response'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'uncovered_part_demand') AND a.metric COLLATE Latin1_General_100_BIN2=N'uncovered_part_demand' THEN N'Parts still needed'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'response_cost') AND a.metric COLLATE Latin1_General_100_BIN2=N'response_cost' THEN N'Response cost'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'protected_customer_orders') AND a.metric COLLATE Latin1_General_100_BIN2=N'protected_customer_orders' THEN N'Protected customer orders'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'revenue_protected') AND a.metric COLLATE Latin1_General_100_BIN2=N'revenue_protected' THEN N'Revenue protected'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'margin_protected') AND a.metric COLLATE Latin1_General_100_BIN2=N'margin_protected' THEN N'Margin protected'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'otif_loss_percentage') AND a.metric COLLATE Latin1_General_100_BIN2=N'otif_loss_percentage' THEN N'Service-target exposure'
   WHEN DATALENGTH(a.metric)=DATALENGTH(N'remaining_alpha_recovery_date') AND a.metric COLLATE Latin1_General_100_BIN2=N'remaining_alpha_recovery_date' THEN N'Remaining Supplier Alpha recovery date'
   ELSE N'Result metric not recognized' END AS metric_display_name,
 a.predicted_value,a.observed_value,a.unit,a.observation_kind,
 CASE
   WHEN DATALENGTH(a.observation_kind)=DATALENGTH(N'actual') AND a.observation_kind COLLATE Latin1_General_100_BIN2=N'actual' THEN N'Actual'
   WHEN DATALENGTH(a.observation_kind)=DATALENGTH(N'simulated') AND a.observation_kind COLLATE Latin1_General_100_BIN2=N'simulated' THEN N'Simulated'
   ELSE N'Outcome type not recognized' END AS observation_kind_display,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 CONVERT(datetime2(6),SWITCHOFFSET(a.projection_updated_at,'+00:00')) AS projection_updated_at,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.decision_id)),2) AS decision_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.action_id)),2) AS action_key
FROM analytics.action_outcomes a
