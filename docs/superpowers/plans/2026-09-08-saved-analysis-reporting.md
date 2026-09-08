# Saved Analysis Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply explicit, immutable case/analysis/option and case/analysis/record SQL projections for the approved focused report pages.

**Architecture:** Add saved-analysis reporting views to the existing analytics script. Keep the four existing compatibility views and schema-version 12 runtime contract intact; the new report release checks its own required view and column manifest before changing the semantic model. Resolve governing approved options through the case's current decision and that decision's analysis, independently of the case's current analysis.

**Tech Stack:** Fabric SQL Database T-SQL, SQLAlchemy, pyodbc, pytest, existing `GO` batch runner.

## Global Constraints

- Approved specification: `docs/superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md`; delivery stage 3 in `docs/superpowers/plans/2026-09-08-planner-experience-delivery.md`.
- “Project response options at case/analysis/option grain; do not duplicate totals through joins.”
- “Project supporting records at case/analysis/source-record grain, keeping their typed fields and provenance tied to the immutable saved analysis.”
- “Do not mutate immutable analysis material, source bundles, hashes, or stored citations, and do not weaken existing trusted-URL validation or approval rules.”
- “Dates and currency must be formatted without timezone-related day shifts or invented units.” Money is `decimal(19,4)` with no currency column or currency symbol: the domain does not persist currency.
- No Power BI artifacts, live database migrations, permissions, deployment, case creation in the shared environment, approval, or playback in this stage. Test rows below exist only in a dedicated disposable local database.
- Preserve the two packaged scripts, their order, one transaction per batch, idempotent retry, operational version 11 followed by analytics version 12, and exact runtime version checking. Do not change `001_operational_schema.sql`, `integrations/fabric/schema.py`, or `integrations/fabric/health.py`.
- Recommendations and option predictions are saved calculations, never observed outcomes or approvals. Do not reconstruct OTIF line counts from a rounded percentage. The current option payload has no persisted numerator/denominator; leave those unavailable.

## Files and interfaces

Modify `fabric/sql/002_analytics_views.sql` in dependency order: analytics schema; new `analytics.report_scalar` validation function; `saved_analyses`; `saved_options`; `saved_records`; `saved_record_evidence`; the four existing compatibility views in their existing order; new `case_reporting`; final existence/version guard. In particular, `app.decision_projection` must exist before creating `case_reporting` on a fresh database. Modify `tests/integrations/test_fabric_sql_scripts.py` only for the additive view inventory expectations. Create `tests/integrations/test_saved_analysis_reporting_sql.py` for actual local SQL execution. Extend `fabric/sql/README.md` with the validation and release gate below.

New report-facing views:

| View | Grain | Required identity and behavior |
| --- | --- | --- |
| `analytics.saved_analyses` | case/analysis | All historical versions; independent `payload_state` and `snapshot_state`, saved timestamps, runtime, scenario, calculation version, recommendation ID. Invalid snapshot has no record facts; invalid payload identity has no option facts. |
| `analytics.saved_options` | case/analysis/option | Unique option IDs only; duplicate IDs excluded, with raw counts available through saved analysis payload. Baseline identified by `no_mitigation`, not an option-ID convention. |
| `analytics.saved_records` | case/analysis/family/record | Typed stock, production, customer-line, disruption, shipment, transfer, qualification facts. Duplicate identities excluded. Source evidence joins must be unique and exact. |
| `analytics.saved_record_evidence` | case/analysis/family/record | Unique evidence and material membership, exact identity, explicit live versus fixture provenance, nullable recorded timestamps. |
| `analytics.case_reporting` | case | Current analysis and governing decision lineage as separate columns. Baseline/recommended/approved metrics never share an implicit basis. |

`saved_analyses` also exposes internal `payload_json` and `snapshot_json` to simplify the dependent views. They are not imported into the semantic model. `payload_state` validates persisted case/analysis/material identity independently of `snapshot_state`; a missing snapshot does not erase otherwise valid saved options. Invalid payload identity suppresses options. The persisted domain stores runtime/scenario in material and typed SQL columns; API top-level runtime/scenario are derived and must not be required as additional stored JSON keys. `saved_options` exposes the explicit scalar columns in Task 2 plus JSON arrays for assumptions, blockers, prerequisite roles, protected customer orders, and evidence identities; the later model may normalize those arrays without changing their meaning. `saved_records` exposes a common typed column superset (irrelevant family columns are null). `record_family` disambiguates repeated IDs across families. Composite filtering always includes case and analysis even though analysis IDs are currently globally unique.

One internal scalar-validation function is in scope to prevent repeated, inconsistent coercion rules across views. It is not part of the runtime version-12 health contract. Required numeric fields accept JSON numbers with whole nonnegative digits only, within SQL `int`; out-of-range facts are unavailable. Money accepts only the domain's serialized JSON strings with exactly two decimal places and a representable `decimal(19,4)` value. Dates require exact `YYYY-MM-DD` round-trip identity. Timestamps require explicit ISO time/zone and at most six fractional digits, matching the SQL timestamp precision. Explicit null optional dates/flags/timestamps are supported; missing or malformed required provenance fields fail. Invalid optional business facts are null rather than rounded/coerced, and do not establish availability of a record that requires them.

The deployment target is **SQL database in Microsoft Fabric**, through its database TDS endpoint. Microsoft's [CREATE FUNCTION reference](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-function-transact-sql) explicitly includes this product and supports Transact-SQL scalar functions with `CREATE OR ALTER`. Its [UDF limitations and scalar examples](https://learn.microsoft.com/en-us/sql/relational-databases/user-defined-functions/create-user-defined-functions-database-engine) permit local variables, assignment and SELECT aggregation; this helper uses no dynamic SQL, temporary tables, state changes or prohibited side-effecting functions. The [OPENJSON reference](https://learn.microsoft.com/en-us/sql/t-sql/functions/openjson-transact-sql) and [TRY_CONVERT reference](https://learn.microsoft.com/en-us/sql/t-sql/functions/try-convert-transact-sql) both explicitly include SQL database in Microsoft Fabric. These establish applicability of the component constructs; the composed helper and views still require the runtime gate below. Do not apply Fabric Warehouse UDF inlining restrictions or assume these objects deploy to the read-only SQL analytics endpoint.

## Task 1: Build a real SQL acceptance harness and the immutable analysis base

**Files:** Create `tests/integrations/test_saved_analysis_reporting_sql.py`; modify `fabric/sql/002_analytics_views.sql`.

**Interfaces:** Consume existing `app.analysis_versions` and `apply_fabric_schema(engine)`. Produce `analytics.saved_analyses` and a localhost-only SQL fixture. No query references mutable `app.operational_snapshots`.

- [ ] Add the following complete test module. The selected database must be newly created and dedicated to this suite. The fixture refuses remote hosts and any database name outside `supply_response_projection_test_…`; it does not discover credentials or use Fabric environment variables.

```python
import json
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from integrations.fabric.schema import apply_fabric_schema


@pytest.fixture(scope="module")
def engine():
    raw = os.environ.get("SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL")
    if not raw:
        pytest.skip("local SQL execution gate not configured")
    url = make_url(raw)
    assert url.drivername == "mssql+pyodbc"
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    assert (url.database or "").startswith("supply_response_projection_test_")
    assert "odbc_connect" not in url.query
    assert "server" not in {key.lower() for key in url.query}
    value = create_engine(url)
    with value.connect() as connection:
        assert connection.scalar(text(
            "SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()"
        )) >= 130
        assert connection.scalar(text(
            "SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s "
            "ON s.schema_id=t.schema_id WHERE s.name IN ('app','analytics')"
        )) == 0, "Use a fresh dedicated test database"
    apply_fabric_schema(value)
    apply_fabric_schema(value)
    yield value
    value.dispose()


def rows(engine, query, **parameters):
    with engine.connect() as connection:
        return list(connection.execute(text(query), parameters).mappings())


def seed(engine, *, snapshot=None, options=None, recommendation="response"):
    case_id, analysis_id = str(uuid4()), str(uuid4())
    snapshot = dict(snapshot or {})
    at = "2026-09-01T09:00:00-05:00"
    snapshot = {"scenario_effective_time": at, "scenario_timezone": "America/Chicago",
                "analysis_horizon_start": at, "analysis_horizon_end": "2026-09-10",
                "inventory_positions": [], "production_orders": [], "customer_orders": [],
                "disruption": {}, **snapshot, "case_id": case_id, "runtime_mode": "live"}
    payload = {
        "case_id": case_id, "analysis_id": analysis_id,
        "material": {
            "case_id": case_id, "runtime_mode": "live", "template_id": "RL-001",
            "corpus": "demo_corpus", "evidence": [],
            "scenario_effective_time": "2026-09-01T09:00:00-05:00",
            "calculation_version": "test-v1",
            "operational_snapshot_json": json.dumps(snapshot),
        },
        "response_options": options or [],
        "ranking": {"recommended_option_id": recommendation},
        "evidence_items": [],
    }
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT app.case_instances
            (case_id,template_id,purpose,runtime_mode,status,scenario_effective_time,payload_json)
            VALUES (:c,'RL-001','automated_test','live','open',:at,'{}')
        """), {"c": case_id, "at": at})
        connection.execute(text("""
            INSERT app.analysis_versions
            (analysis_id,case_id,material_hash,runtime_mode,analysis_started_at,
             retrieval_window_ends_at,created_at,payload_json)
            VALUES (:a,:c,'test','live',SYSDATETIMEOFFSET(),SYSDATETIMEOFFSET(),
                    SYSDATETIMEOFFSET(),:p)
        """), {"a": analysis_id, "c": case_id, "p": json.dumps(payload)})
    return case_id, analysis_id, payload


def update_payload(engine, analysis_id, payload):
    # Test-only malformed/history fixtures; production never updates saved analysis.
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE app.analysis_versions SET payload_json=:p WHERE analysis_id=:a"
        ), {"a": analysis_id, "p": json.dumps(payload)})


def option(identity, kind="expedite", value="0.00"):
    value = f"{Decimal(value):.2f}"
    return {
        "option_id": identity, "option_kind": kind, "name": identity,
        "executable": False, "active_mitigation": kind != "no_mitigation",
        "predicted": {"revenue_at_risk": value, "margin_at_risk": value,
                      "response_cost": value, "uncovered_part_demand": 0,
                      "otif_loss_percentage": 0,
                      "protected_customer_order_ids": []},
        "blocking_codes": ["QUALIFICATION_PENDING"], "assumptions": [],
        "prerequisite_roles": [], "evidence_ids": [],
    }


def test_snapshot_is_full_length_and_identity_checked(engine):
    c, a, payload = seed(engine, snapshot={"padding": "x" * 5000})
    result = rows(engine, "SELECT * FROM analytics.saved_analyses WHERE analysis_id=:a", a=a)[0]
    assert result["case_id"] == c
    assert result["snapshot_state"] == "available"
    assert len(result["snapshot_json"]) > 5000
    for invalid in ("{", "null", "[]", json.dumps({"case_id": "wrong", "runtime_mode": "live"})):
        payload["material"]["operational_snapshot_json"] = invalid
        update_payload(engine, a, payload)
        result = rows(engine, "SELECT * FROM analytics.saved_analyses WHERE analysis_id=:a", a=a)[0]
        assert result["snapshot_state"] == "unavailable"
        assert result["snapshot_json"] is None


def test_options_preserve_zero_null_false_and_reject_duplicate_identity(engine):
    missing = option("missing")
    missing["predicted"] = None
    c, a, _ = seed(engine, options=[option("baseline", "no_mitigation"),
                                   option("response"), missing,
                                   option("duplicate"), option("duplicate")])
    result = rows(engine, "SELECT * FROM analytics.saved_options WHERE case_id=:c AND analysis_id=:a", c=c, a=a)
    by_id = {row["option_id"]: row for row in result}
    assert set(by_id) == {"baseline", "response", "missing"}
    assert by_id["baseline"]["is_baseline"]
    assert by_id["response"]["is_recommended"]
    assert by_id["response"]["revenue_at_risk"] == 0
    assert by_id["response"]["executable"] is False
    assert by_id["missing"]["revenue_at_risk"] is None


@pytest.mark.parametrize("kind,value,expected", [
    ("integer", 0, "0"), ("integer", "0", None), ("integer", "", None),
    ("integer", 0.5, None), ("integer", True, None), ("integer", 2147483648, None),
    ("money", "0.00", "0.00"), ("money", "", None), ("money", "1.239", None),
    ("money", 0, None), ("money", "1e2", None), ("money", " 0.00", None),
    ("date", "2026-09-06", "2026-09-06"), ("date", "", None),
    ("date", "2026-9-6", None), ("date", "09/06/2026", None),
    ("date", "2026-02-30", None), ("date", "2026-09-06 ", None),
    ("nullable_date", None, "#null"), ("nullable_flag", False, "false"),
    ("flag", "false", None), ("nullable_instant", None, "#null"),
    ("instant", "2026-09-01T09:00:00-05:00", "2026-09-01T09:00:00-05:00"),
    ("instant", "2026-09-01", None), ("instant", "2026-09-01T09:00:00", None),
    ("instant", "2026-09-01T09:00:00.1234567Z", None),
])
def test_strict_scalar_semantics(engine, kind, value, expected):
    result = rows(engine, "SELECT analytics.report_scalar(:p,N'value',:kind) AS value",
                  p=json.dumps({"value": value}), kind=kind)[0]
    assert result["value"] == expected


@pytest.mark.parametrize("payload", ['{}', '{"value":0,"value":0}', '{'])
def test_missing_duplicate_or_malformed_scalar_is_unavailable(engine, payload):
    assert rows(engine, "SELECT analytics.report_scalar(:p,N'value',N'integer') AS value",
                p=payload)[0]["value"] is None


def test_snapshot_absence_is_separate_from_payload_identity(engine):
    c, a, payload = seed(engine, options=[option("response")])
    payload["material"]["operational_snapshot_json"] = "{"
    update_payload(engine, a, payload)
    result = rows(engine, "SELECT payload_state,snapshot_state FROM analytics.saved_analyses WHERE analysis_id=:a", a=a)[0]
    assert result == {"payload_state": "available", "snapshot_state": "unavailable"}
    assert len(rows(engine, "SELECT * FROM analytics.saved_options WHERE analysis_id=:a", a=a)) == 1
    payload["case_id"] = "wrong"
    update_payload(engine, a, payload)
    assert rows(engine, "SELECT * FROM analytics.saved_options WHERE analysis_id=:a", a=a) == []


@pytest.mark.parametrize("field,value", [
    ("template_id", "other"), ("corpus", "real_business"),
    ("scenario_effective_time", "2026-09-02T09:00:00-05:00"),
    ("runtime_mode", "fallback"), ("case_id", "wrong"),
])
def test_material_envelope_mismatch_suppresses_all_facts(engine, field, value):
    c, a, payload = seed(engine, options=[option("response")])
    payload["material"][field] = value
    update_payload(engine, a, payload)
    result = rows(engine, "SELECT payload_state,snapshot_state FROM analytics.saved_analyses WHERE analysis_id=:a", a=a)[0]
    assert result == {"payload_state": "unavailable", "snapshot_state": "unavailable"}
    assert rows(engine, "SELECT * FROM analytics.saved_options WHERE analysis_id=:a", a=a) == []


@pytest.mark.parametrize("field,value", [
    ("scenario_timezone", "UTC"), ("analysis_horizon_end", "2026-9-10"),
    ("analysis_horizon_start", ""), ("inventory_positions", {}),
    ("scenario_effective_time", "2026-09-02T09:00:00-05:00"),
])
def test_snapshot_envelope_mismatch_preserves_only_valid_options(engine, field, value):
    c, a, payload = seed(engine, options=[option("response")])
    snapshot = json.loads(payload["material"]["operational_snapshot_json"])
    snapshot[field] = value
    payload["material"]["operational_snapshot_json"] = json.dumps(snapshot)
    update_payload(engine, a, payload)
    result = rows(engine, "SELECT payload_state,snapshot_state FROM analytics.saved_analyses WHERE analysis_id=:a", a=a)[0]
    assert result == {"payload_state": "available", "snapshot_state": "unavailable"}
    assert len(rows(engine, "SELECT * FROM analytics.saved_options WHERE analysis_id=:a", a=a)) == 1
```

- [ ] Run `uv run --extra dev pytest tests/integrations/test_saved_analysis_reporting_sql.py -rs`. With a local database, the first run must fail on the missing view. Without a database, record SKIPPED, not PASS of SQL semantics; continue authoring and run the later SQL gate before release.
- [ ] Insert this complete helper after analytics schema creation. Every successful return has checked JSON type, unique property membership, lexical shape and SQL representability. `#null` is an internal sentinel for an explicit JSON null in a nullable field, never a report value; malformed or absent properties return SQL NULL. It avoids treating blanks as numeric zero, accepting flexible calendar-date formats, or silently rounding decimals. Keep the final casts in the views: they consume only checked helper results.

```sql
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
```

- [ ] Insert this base view after the helper. Snapshot sections are independently inspectable, but the supporting-record envelope requires the three arrays and disruption object used by the resolver. Payload identity remains separate from snapshot availability. Native SQL row timestamps already have enforced types; scenario equality compares instants rather than displayed timezone strings.

```sql
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
OUTER APPLY OPENJSON(a.payload_json) WITH (
    snapshot_json nvarchar(max) '$.material.operational_snapshot_json'
) extracted
OUTER APPLY (SELECT CASE WHEN ISJSON(extracted.snapshot_json)=1
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
```

- [ ] Run the snapshot test against local SQL, then commit this task's files after review. No runtime claim from string matching. `OPENJSON` requires compatibility level 130 and supports `nvarchar(max)` extraction; `JSON_VALUE` cannot safely extract the long encoded snapshot. See [Microsoft OPENJSON reference](https://learn.microsoft.com/en-us/sql/t-sql/functions/openjson-transact-sql) and [Microsoft JSON troubleshooting](https://learn.microsoft.com/en-us/sql/relational-databases/json/solve-common-issues-with-json-sql-server). These references were consulted using the Microsoft docs skill; Learn MCP was unavailable.

## Task 2: Expose saved options without recommendation or baseline ambiguity

**Files:** Modify `fabric/sql/002_analytics_views.sql`; test `tests/integrations/test_saved_analysis_reporting_sql.py`.

**Interfaces:** Consume `analytics.saved_analyses`; produce typed `analytics.saved_options`. Identity comparisons use binary collation. Null predictions retain the option with null metrics; duplicate option IDs yield no option fact for that identity, never `TOP (1)`.

- [ ] Run the existing option test and confirm missing-view failure against local SQL.
- [ ] Insert the following complete view after `saved_analyses`.

```sql
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
```

- [ ] Run both tests against local SQL; run `uv run --extra dev pytest tests/analysis/test_rl001_options.py tests/analysis/test_ranking.py` to confirm baseline/option interpretation against the unchanged calculation contract. Commit the task after checks pass.

## Task 3: Project exact supporting records and stock/order breakdowns

**Files:** Modify `fabric/sql/002_analytics_views.sql`; test `tests/integrations/test_saved_analysis_reporting_sql.py`.

**Interfaces:** Consume `saved_analyses.snapshot_json` only. Produce record rows for `disruption`, `shipment`, `transfer`, `qualification`, `inventory`, `production_order`, `customer_order_line`. Preserve source IDs; names/roles belong to the later supported display mapping. Stock availability is `on_hand-quality_hold-protected_allocation`, preserving negative values if persisted rather than inventing a zero floor. Customer line revenue is quantity times unit revenue and is a line value, not automatically projected revenue at risk.

- [ ] Append the following runtime test and run it to observe missing-view failure.

```python
def test_stock_order_and_historical_record_grains(engine):
    stock = {"inventory_id": "shared", "part_id": "P", "plant_id": "CHI",
             "on_hand": 10, "quality_hold": 2, "protected_allocation": 8}
    customer = {"customer_order_line_id": "line", "customer_id": "C",
                "product_id": "FG", "plant_id": "CHI", "quantity": 2,
                "unit_revenue": "12.50", "unit_margin": "0.00",
                "due_date": "2026-09-06", "production_order_id": "production"}
    c, a, payload = seed(engine, snapshot={"inventory_positions": [stock],
                                         "customer_orders": [customer]})
    c2, a2, _ = seed(engine, snapshot={"inventory_positions": [dict(stock, on_hand=99)]})
    result = rows(engine, "SELECT * FROM analytics.saved_records WHERE case_id=:c AND analysis_id=:a", c=c, a=a)
    by_family = {row["record_family"]: row for row in result}
    assert by_family["inventory"]["usable_inventory"] == 0
    assert by_family["customer_order_line"]["line_revenue"] == 25
    assert str(by_family["customer_order_line"]["due_date"]) == "2026-09-06"
    assert rows(engine, "SELECT * FROM analytics.saved_records WHERE case_id=:c AND analysis_id=:a", c=c, a=a2) == []
    snapshot = json.loads(payload["material"]["operational_snapshot_json"])
    snapshot["inventory_positions"].append(stock)
    payload["material"]["operational_snapshot_json"] = json.dumps(snapshot)
    update_payload(engine, a, payload)
    assert rows(engine, "SELECT * FROM analytics.saved_records WHERE analysis_id=:a AND record_family='inventory'", a=a) == []


@pytest.mark.parametrize("field,value,column", [
    ("quantity", "", "quantity"), ("quantity", 1.5, "quantity"),
    ("due_date", "", "due_date"), ("due_date", "09/06/2026", "due_date"),
    ("incremental_cost_per_unit", "0.001", "incremental_cost_per_unit"),
])
def test_malformed_required_record_fact_never_becomes_available_zero(engine, field, value, column):
    receipt = {"receipt_id": "receipt", "supplier_id": "supplier", "part_id": "part",
               "plant_id": "CHI", "quantity": 1, "due_date": "2026-09-06",
               "incremental_cost_per_unit": "0.00", field: value}
    c, a, _ = seed(engine, snapshot={"alpha_expedite": receipt,
        "inventory_positions": [{"inventory_id": "stock", "part_id": "part", "plant_id": "CHI",
                                  "on_hand": 0, "quality_hold": 0, "protected_allocation": 0}]})
    result = rows(engine, "SELECT * FROM analytics.saved_records WHERE analysis_id=:a AND record_family='shipment'", a=a)[0]
    assert result["record_state"] == "unavailable"
    assert result[column] is None
    inventory = rows(engine, "SELECT * FROM analytics.saved_records WHERE analysis_id=:a AND record_family='inventory'", a=a)[0]
    assert inventory["record_state"] == "available"
    assert inventory["usable_inventory"] == 0
    assert inventory["due_date"] is None  # Inventory has no due-date contract.


@pytest.mark.parametrize("status,expected", [
    ("approved", "available"), ("pending", "available"),
    ("APPROVED", "unavailable"), ("Pending", "unavailable"),
])
def test_qualification_status_uses_exact_enum(engine, status, expected):
    c, a, _ = seed(engine, snapshot={"beta_qualification": {
        "qualification_id": "qualification", "supplier_id": "supplier", "part_id": "part",
        "evidence_ref": "proof", "status": status, "audit_complete": False,
        "first_article_complete": None, "effective_date": None, "expected_decision_date": None,
    }})
    result = rows(engine, "SELECT record_state FROM analytics.saved_records WHERE analysis_id=:a AND record_family='qualification'", a=a)[0]
    assert result["record_state"] == expected
```

- [ ] Insert this view. String extraction precedes `TRY_CONVERT` so bad numeric/date fields become unavailable rather than throwing or turning into zero. Raw family JSON remains internal; `record_json` is not a report column.

```sql
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
```

- [ ] Execute the runtime tests. Confirm stock/order figures are at record grain and never joined to option totals. Commit the task after review.

## Task 4: Resolve evidence provenance and availability without guessing

**Files:** Modify `fabric/sql/002_analytics_views.sql`; test `tests/integrations/test_saved_analysis_reporting_sql.py`.

**Interfaces:** Add `analytics.saved_record_evidence`, grain case/analysis/family/record. It is a one-to-one optional companion to `saved_records`. Report detail selection requires exactly one record plus exactly one matching evidence row with state `available` for shipment/transfer/qualification. An external Fabric action additionally requires `provenance=saved_fabric`; fallback fixture rows are explicitly `demo_fixture` and never relabeled as live retrieval. Stock/order/disruption pages identify saved snapshot provenance and do not invent per-record retrieval times.

- [ ] Add this view after `saved_records`. It resolves expected evidence ID, unique membership in both saved evidence arrays, every material identity field, exact source identity, operational-fact kind, and live/fixture provenance. Shipment/transfer evidence IDs equal the record ID; qualification evidence ID equals `evidence_ref`. Duplicate evidence IDs or source IDs remain unavailable even if duplicate rows look identical. Null timestamps are supported with an unavailable-time label; malformed or omitted timestamp fields are rejected. This matches the resolver's saved-evidence inspection contract without introducing a retrieval-window approval rule.

```sql
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
    AND f.retrieved_at IS NOT NULL AND f.source_timestamp IS NOT NULL
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
```

- [ ] Append and run the complete provenance tests below. An explicit null retrieval time remains null and does not become “now.” Malformed or missing provenance fields prevent resolution. A fallback fixture remains inspectable only with fixture provenance and no external Fabric action.

```python
@pytest.mark.parametrize("family,member,key,prefix", [
    ("shipment", "alpha_expedite", "receipt_id", "fabric.supply_receipt/"),
    ("transfer", "transfer", "transfer_id", "fabric.inventory_transfer/"),
    ("qualification", "beta_qualification", "qualification_id", "fabric.qualification/"),
])
def test_exact_evidence_and_duplicate_or_missing_provenance(engine, family, member, key, prefix):
    expected_id = "proof" if family == "qualification" else "record"
    record = {key: "record", "evidence_ref": "proof", "audit_complete": False,
              "first_article_complete": None, "effective_date": None, "expected_decision_date": None,
              "supplier_id": "supplier", "part_id": "part", "plant_id": "CHI",
              "source_plant_id": "DAL", "destination_plant_id": "CHI",
              "quantity": 1, "due_date": "2026-09-06", "dispatch_date": "2026-09-05",
              "arrival_date": "2026-09-06", "incremental_cost_per_unit": "0.00", "status": "pending"}
    c, a, payload = seed(engine, snapshot={member: record})
    times = rows(engine, "SELECT analysis_started_at FROM app.analysis_versions WHERE analysis_id=:a", a=a)[0]
    evidence = {"evidence_id": expected_id, "case_id": c, "source_id": prefix+"record",
                "kind": "operational_fact",
                "source_system": "fabric", "retrieved_for_analysis_id": a,
                "runtime_mode": "live", "synthetic": False,
                "retrieved_at": times["analysis_started_at"].isoformat(),
                "source_timestamp": None}
    query = "SELECT * FROM analytics.saved_record_evidence WHERE case_id=:c AND analysis_id=:a AND record_family=:f"
    for items, material, expected in [
        ([evidence], [evidence], "available"),
        ([evidence, evidence], [evidence], "unavailable"),
        ([evidence, dict(evidence, source_id="different")], [evidence], "unavailable"),
        ([evidence, dict(evidence, evidence_id="different")], [evidence], "unavailable"),
        ([evidence], [evidence, evidence], "unavailable"),
        ([evidence], [], "unavailable"),
        ([dict(evidence, evidence_id="wrong")], [dict(evidence, evidence_id="wrong")], "unavailable"),
        ([dict(evidence, kind="source_statement")], [dict(evidence, kind="source_statement")], "unavailable"),
        ([dict(evidence, synthetic=True)], [dict(evidence, synthetic=True)], "unavailable"),
        ([dict(evidence, synthetic="false")], [dict(evidence, synthetic="false")], "unavailable"),
        ([evidence], [dict(evidence, synthetic=True)], "unavailable"),
        ([evidence], [dict(evidence, source_id="other")], "unavailable"),
        ([evidence], [dict(evidence, source_timestamp="2026-09-01T00:00:00Z")], "unavailable"),
        ([dict(evidence, retrieved_for_analysis_id="other")], [evidence], "unavailable"),
        ([dict(evidence, retrieved_at=None)], [evidence], "available"),
        ([dict(evidence, retrieved_at="")], [evidence], "unavailable"),
        ([dict(evidence, source_timestamp="")], [dict(evidence, source_timestamp="")], "unavailable"),
        ([{k:v for k,v in evidence.items() if k != "source_timestamp"}], [evidence], "unavailable"),
        ([dict(evidence, source_id=prefix+"RECORD")], [evidence], "unavailable"),
        ([], [], "unavailable"),
    ]:
        payload["evidence_items"] = items
        payload["material"]["evidence"] = material
        update_payload(engine, a, payload)
        result = rows(engine, query, c=c, a=a, f=family)[0]
        assert result["evidence_state"] == expected
        assert result["source_timestamp"] is None
        assert result["provenance"] == ("saved_fabric" if expected == "available" else None)
        if items and items[0].get("retrieved_at") is None:
            assert result["retrieved_at"] is None
    if family == "qualification":
        record = rows(engine, "SELECT audit_complete FROM analytics.saved_records WHERE analysis_id=:a", a=a)[0]
        assert record["audit_complete"] is False

    fixture = dict(evidence, runtime_mode="fallback", source_system="synthetic_fixture",
                   synthetic=True, source_id="RL-SOURCE-"+expected_id, retrieved_at=None)
    snapshot = json.loads(payload["material"]["operational_snapshot_json"])
    snapshot["runtime_mode"] = "fallback"
    payload["material"].update(runtime_mode="fallback", evidence=[fixture],
                               operational_snapshot_json=json.dumps(snapshot))
    payload["evidence_items"] = [fixture]
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.case_instances SET runtime_mode='fallback' WHERE case_id=:c"), {"c": c})
        connection.execute(text("UPDATE app.analysis_versions SET runtime_mode='fallback' WHERE analysis_id=:a"), {"a": a})
    update_payload(engine, a, payload)
    result = rows(engine, query, c=c, a=a, f=family)[0]
    assert result["evidence_state"] == "available"
    assert result["provenance"] == "demo_fixture"
    assert result["synthetic"] is True
    assert result["retrieved_at"] is None
```

- [ ] Commit the task after the actual SQL test passes. This is an inspection projection, not an approval policy change.

## Task 5: Add case summary with independent governing-decision lineage

**Files:** Modify `fabric/sql/002_analytics_views.sql`; test `tests/integrations/test_saved_analysis_reporting_sql.py`.

**Interfaces:** Consume `app.case_projection`, `app.decision_projection`, `saved_analyses`, and `saved_options`. Produce `analytics.case_reporting` with separate `current_analysis_id`, `decision_analysis_id`, `approved_option_id`, recommendation and baseline identities, and four metrics for each basis. An approved option is matched only in the decision's saved analysis. Rejected decisions never populate approved metrics.

- [ ] Insert this complete view after the four existing compatibility views and before the final guard. In a fresh database `app.decision_projection` must already exist. Baseline selection requires exactly one baseline option; no arbitrary TOP or latest-created selection is allowed. The existing command-center compatibility projection remains unchanged for the old deployed model until coordinated release.

```sql
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
```

- [ ] Append this lineage test and execute it against local SQL. It creates a second analysis with the same case while leaving a governing decision on the original analysis; all rows remain test-only.

```python
def test_new_analysis_does_not_replace_governing_approved_prediction(engine):
    c, old, payload = seed(engine, options=[option("baseline", "no_mitigation", "100"),
                                          option("response", value="20"),
                                          option("chosen", value="30")])
    new, decision = str(uuid4()), str(uuid4())
    new_payload = dict(payload, analysis_id=new,
                       response_options=[option("baseline", "no_mitigation", "200"),
                                         option("response", value="5")])
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT app.analysis_versions
            (analysis_id,case_id,material_hash,runtime_mode,analysis_started_at,
             retrieval_window_ends_at,created_at,payload_json)
            SELECT :n,case_id,'new','live',analysis_started_at,retrieval_window_ends_at,
                   DATEADD(second,1,created_at),:p FROM app.analysis_versions WHERE analysis_id=:a
        """), {"n": new, "p": json.dumps(new_payload), "a": old})
        connection.execute(text("""
            INSERT app.decisions
            (decision_id,case_id,analysis_id,idempotency_key,kind,runtime_mode,decided_at,payload_json)
            VALUES (:d,:c,:a,:d,'approved','live',SYSDATETIMEOFFSET(),:p)
        """), {"d": decision, "c": c, "a": old,
               "p": json.dumps({"selected_option_id": "chosen"})})
        connection.execute(text("""
            INSERT app.case_projection
            (case_id,purpose,status,runtime_mode,scenario_effective_time,
             current_analysis_id,current_decision_id,payload_json)
            VALUES (:c,'automated_test','open','live',SYSDATETIMEOFFSET(),:n,:d,'{}')
        """), {"c": c, "n": new, "d": decision})
    result = rows(engine, "SELECT * FROM analytics.case_reporting WHERE case_id=:c", c=c)[0]
    assert result["current_analysis_id"] == new
    assert result["decision_analysis_id"] == old
    assert result["baseline_revenue_at_risk"] == 200
    assert result["recommended_revenue_at_risk"] == 5
    assert result["approved_revenue_at_risk"] == 30
    assert rows(engine, "SELECT revenue_at_risk FROM analytics.saved_options WHERE case_id=:c AND analysis_id=:a AND option_id='response'", c=c, a=old)[0]["revenue_at_risk"] == 20
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.decisions SET kind='rejected',payload_json='{}' WHERE decision_id=:d"), {"d": decision})
    assert rows(engine, "SELECT approved_revenue_at_risk FROM analytics.case_reporting WHERE case_id=:c", c=c)[0]["approved_revenue_at_risk"] is None
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.case_projection SET current_analysis_id=NULL,current_decision_id=NULL WHERE case_id=:c"), {"c": c})
    result = rows(engine, "SELECT * FROM analytics.case_reporting WHERE case_id=:c", c=c)[0]
    assert result["recommended_revenue_at_risk"] is None
    assert result["baseline_revenue_at_risk"] is None
    assert result["approved_revenue_at_risk"] is None


def test_absent_recommendation_and_ambiguous_baselines_do_not_pick_an_option(engine):
    c, a, _ = seed(engine, recommendation=None,
                   options=[option("baseline-1", "no_mitigation", "10"),
                            option("baseline-2", "no_mitigation", "20")])
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT app.case_projection
            (case_id,purpose,status,runtime_mode,scenario_effective_time,
             current_analysis_id,payload_json)
            VALUES (:c,'automated_test','open','live',SYSDATETIMEOFFSET(),:a,'{}')
        """), {"c": c, "a": a})
    result = rows(engine, "SELECT * FROM analytics.case_reporting WHERE case_id=:c", c=c)[0]
    assert result["recommended_option_id"] is None
    assert result["recommended_revenue_at_risk"] is None
    assert result["baseline_option_id"] is None
    assert result["baseline_revenue_at_risk"] is None
```

- [ ] Run all local reporting SQL tests, then commit after review.

## Task 6: Preserve deployment compatibility and record the report release gate

**Files:** Modify `tests/integrations/test_fabric_sql_scripts.py`, `fabric/sql/002_analytics_views.sql`, `fabric/sql/README.md`.

**Interfaces:** Existing readiness still means version 12 and the original four views. Reporting deployment separately requires all five added views. No third SQL script or startup migration is introduced.

- [ ] Extend the final SQL existence guard with these six OR terms (one function and five views), before the existing `THROW`, leaving both version statements unchanged:

```sql
    OR OBJECT_ID(N'analytics.report_scalar', N'FN') IS NULL
    OR OBJECT_ID(N'analytics.saved_analyses', N'V') IS NULL
    OR OBJECT_ID(N'analytics.saved_options', N'V') IS NULL
    OR OBJECT_ID(N'analytics.saved_records', N'V') IS NULL
    OR OBJECT_ID(N'analytics.saved_record_evidence', N'V') IS NULL
    OR OBJECT_ID(N'analytics.case_reporting', N'V') IS NULL
```

There are five added views and nine total views, plus one internal scalar function. Use that inventory in tests and release checks; the internal base and companion provenance view are included. Preserve the original four-view health query unchanged.

- [ ] In `test_schemas_views_and_version_publication_are_idempotent`, change only the CREATE OR ALTER VIEW count from 4 to 9. In `test_real_script_sequence_promotes_readiness_only_after_analytics`, append these entries to its expected `engine.views` set:

```python
        "analytics.saved_analyses",
        "analytics.saved_options",
        "analytics.saved_records",
        "analytics.saved_record_evidence",
        "analytics.case_reporting",
```

Do not change `_SequencedFabricEngine.execute`'s required four runtime views or `FABRIC_SCHEMA_VERSION`. Its regex model tests application sequencing only, not SQL semantics.

- [ ] Add this complete local deployment test to the runtime module:

```python
def test_sql_readiness_and_explicit_report_inventory(engine):
    from integrations.fabric.health import check_fabric_health
    assert check_fabric_health(engine).schema_version == 12
    assert rows(engine, "SELECT OBJECT_ID(N'analytics.report_scalar',N'FN') AS object_id")[0]["object_id"] is not None
    expected = {"saved_analyses", "saved_options", "saved_records",
                "saved_record_evidence", "case_reporting"}
    actual = rows(engine, "SELECT v.name FROM sys.views v JOIN sys.schemas s ON s.schema_id=v.schema_id WHERE s.name='analytics'")
    assert expected <= {row["name"] for row in actual}
    for view in sorted(expected):
        # Names come from a constant allowlist, never user input.
        columns = rows(engine, f"SELECT TOP (0) * FROM analytics.{view}")
        assert columns == []
```

- [ ] Append the following documentation to `fabric/sql/README.md`:

```markdown
## Saved-analysis reporting

The additive `analytics.saved_analyses`, `saved_options`, `saved_records`,
`saved_record_evidence`, and `case_reporting` views serve the case/analysis
reporting contract, using the internal `analytics.report_scalar` validation function.
They do not change operational schema version 12 or the
four-view application health contract. The report deployment must check all
five added views, the validation function, and the columns consumed by its model
before refreshing it. The SQL script creates the function before dependent views
and creates the compatibility decision projection before the case-reporting view.

Record pages filter exact case, analysis, family and record ID. Option pages
filter exact case, analysis and option ID. No/multiple selections are a report
selection state, not SQL totals. Zero matched rows mean unavailable; duplicate
identities are excluded. Missing an analysis from an imported model alone does
not establish refresh lag: say it is unavailable unless the app's known saved
analysis and model refresh metadata establish that the report has not caught up.

Use an explicitly provisioned, fresh disposable local SQL Server database named
`supply_response_projection_test_` followed by a unique suffix. Configure only
`SUPPLY_RESPONSE_LOCAL_REPORTING_SQL_URL` as a `mssql+pyodbc` URL with explicit
localhost host and database fields, ODBC Driver 18, and local test credentials.
Do not configure this test through the Fabric live variables. Run:

    uv run --extra dev pytest tests/integrations/test_saved_analysis_reporting_sql.py -rs

A skipped module means SQL execution is outstanding. Before report deployment,
run the complete module on a supported SQL Server 2017-or-later test engine
(compatibility level >=130), retaining its output. SQL Server's support for the
actual host architecture must be established before provisioning; a working
Docker daemon on ARM is not evidence of a supported SQL Server runtime.
Then use the approved release process to
apply both packaged scripts in order to the explicitly selected Fabric SQL
Database and perform read-only exact-case/analysis query comparisons there.
Never substitute SQLite, a Python arithmetic oracle, or regex assertions for
the T-SQL execution gate. A later Fabric gate verifies platform equivalence;
the local engine verifies queries, types, JSON handling and fixture results.

Release SQL first, check new views and consumed columns, then update the existing
semantic model/report and activate app links together. Preserve report/model IDs
and permissions. Roll back the report/model and deactivate new links first;
the additive views may remain. Do not downgrade the operational version or alter
saved payloads as part of rollback.
```

- [ ] Run `uv run --extra dev pytest tests/integrations/test_fabric_schema.py tests/integrations/test_fabric_sql_scripts.py tests/integrations/test_fabric_health.py tests/integrations/test_saved_analysis_reporting_sql.py -rs` and `uv run ruff check tests/integrations/test_saved_analysis_reporting_sql.py`. Commit this stage after runtime SQL passes; if no engine is available, hand off the outstanding gate explicitly and do not describe projections as runtime-verified.

## Later semantic-model/report contract (required next stage, no artifacts here)

- Import scalar report columns explicitly, excluding raw payload and snapshot JSON. Preserve composite case/analysis identity in relationships and exact record/option filters.
- Gate every detail measure on one case, one analysis, one family and one record (or one option). Require `record_state=available`; for shipment/transfer/qualification also require `evidence_state=available`. External Fabric navigation requires `provenance=saved_fabric`; `demo_fixture` is a separately labeled saved fixture and never evidence of a live retrieval. Individual nullable facts remain unavailable. An unavailable/missing record must never reveal a different record or latest version. An unanalyzed case still exists in the case selector and summary with null metrics.
- `saved_records` is not an affected-order risk list by itself: it contains the saved production and customer lines. Present affected plant/product relationships explicitly. Option `protected_customer_order_ids_json` can mark protection by exact saved customer identity; do not infer per-line OTIF classification when a relationship is absent or ambiguous. Do not derive an order-line denominator from rounded percentages.
- Stock sums require explicit selected case/analysis, disruption part and plant. Sum inventory rows once; never after joining to customer orders or response options. Customer-line values are not additive across options. No unrelated case totals are a valid selected-case result.
- Source timestamp, retrieval timestamp, scenario time, analysis time, and import refresh time have different meanings. `synthetic` describes evidence, not service health. No currency metadata exists. Preserve snapshot labels, uncertainty, and blocked executable flags.

## Self-review and known execution gate

Self-review covers the approved data/report scope, five added views plus the scalar validator, dependency-first creation order, fixture INSERTs and checked-in required columns, exact evidence/material membership, live-versus-fixture flags, strict lexical scalar conversion, binary qualification-enum comparison and regression coverage, and the explicit typed aliases. Microsoft documentation explicitly confirms the individual SQL constructs apply to SQL database in Fabric. The five complete Python blocks parse together, with 19 unique functions. Existing schema runner, script-contract and health tests passed (`23 passed`) before this plan revision; those checks validate the unchanged compatibility contract, not the proposed view results.

The initial sandbox Docker diagnostic denial was resolved by the controller's scoped read-only check: the Docker engine is Linux/aarch64 and has no SQL Server container. No compatible SQL test engine has been provisioned; do not infer supported SQL Server execution on ARM or create/download a container during this plan-only task. No local SQL engine was connected or created, and no live database was contacted. Therefore the proposed T-SQL remains unexecuted. Runtime validation of the complete module on a supported, dedicated SQL test database, followed by the separately authorized Fabric read-only projection comparison at coordinated release, is the precise remaining SQL gate.
