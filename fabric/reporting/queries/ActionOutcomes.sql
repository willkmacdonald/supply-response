SELECT a.case_id,a.decision_id,a.selected_option_id,a.record_type,a.action_id,
 a.action_kind,a.action_status,a.metric,a.predicted_value,a.observed_value,
 a.unit,a.observation_kind,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 CONVERT(datetime2(6),SWITCHOFFSET(a.projection_updated_at,'+00:00')) AS projection_updated_at,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.decision_id)),2) AS decision_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.action_id)),2) AS action_key
FROM analytics.action_outcomes a
