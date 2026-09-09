SELECT a.case_id,a.analysis_id,a.runtime_mode,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_started_at,'+00:00')) AS analysis_started_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.retrieval_window_ends_at,'+00:00')) AS retrieval_window_ends_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.analysis_created_at,'+00:00')) AS analysis_created_at,
 CONVERT(datetime2(6),SWITCHOFFSET(a.scenario_effective_time,'+00:00')) AS scenario_effective_time,
 a.calculation_version,a.recommended_option_id,a.payload_state,a.snapshot_state,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.case_id)),2) AS case_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.analysis_id)),2) AS analysis_key,
 CONVERT(varchar(max),CONVERT(varbinary(max),CONVERT(nvarchar(max),a.recommended_option_id)),2) AS recommended_option_key
FROM analytics.saved_analyses a
