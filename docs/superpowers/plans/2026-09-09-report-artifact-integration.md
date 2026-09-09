# Native report artifacts and preflight integration plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Review this complete task before the next implementation task.

**Goal:** Adopt the reviewed native page/model generators as the checked-in Power BI artifact contract, preserving the existing fail-before-auth deployment boundary.

**Architecture:** Generate the eight PBIR pages and five disconnected DirectQuery tables together; verify exact generator equality, pinned Microsoft schemas and Microsoft's TOM deserializer. This is local artifact implementation, not publishing or DAX execution.

**Constraints:** No live calls, case creation, analysis, approval, playback, authentication, deployment, permissions, licenses, dependency changes, schema catalog changes, item identity changes, push or merge. Keep existing SDK/auth ordering, locked NuGet restore, environment substitution and publication order. Preserve unknown/missing values rather than inventing zeros. Saved recommendation is not approval. SQL queries and generator semantics were separately reviewed; changes to those require controller review rather than silent adjustment.

### Task 1: Adopt generated artifacts and strict preflight

**Files:**
- Modify `fabric/deploy.py`.
- Generate `fabric/power-bi/SupplyResponse.Report/definition/pages/**` using the reviewed page generator.
- Generate `fabric/power-bi/SupplyResponse.SemanticModel/definition/model.tmdl`, `relationships.tmdl`, and five `tables/*.tmdl` using the reviewed model generator.
- Modify `tests/fabric/tmdl-validator/Program.cs`, `tests/fabric/test_power_bi_project.py`, and only the necessary query/helper/test-name sections of `tests/fabric/test_power_bi_live.py`.
- Replace `fabric/power-bi/README.md` with the full text below.

- [x] **Step 1: Add the new behavioral and mutation tests described below before replacing artifacts or deployment code.** Run a focused new eight-page or scoped-model assertion to record the expected RED against old artifacts. Keep all existing security/identity/publish/auth-order/locked-build tests; migrate changed behavior, never skip it.

- [x] **Step 2: Apply the full code migrations below and generate both artifact sets.** The source note below supplies concrete replacement definitions and precise insertion locations; reconcile only mechanical style/import changes. Generation commands:
```sh
.venv/bin/python -m fabric.report_pages fabric/power-bi/SupplyResponse.Report/definition
.venv/bin/python -m fabric.report_model fabric/power-bi/SupplyResponse.SemanticModel/definition fabric/reporting/queries
```
The generators retain stable old visual IDs. There are no obsolete model table files beyond the two replaced in place. Verify exact generated inventories rather than deleting unknown files.

- [x] **Step 3: Run verification, fix actual failures and review the complete diff.**
```sh
.venv/bin/pytest tests/fabric/test_report_generators.py tests/fabric/test_power_bi_project.py tests/fabric/test_schema_updater.py -o addopts='' -q
.venv/bin/ruff check fabric/deploy.py tests/fabric/test_power_bi_project.py tests/fabric/test_power_bi_live.py
.venv/bin/python -m fabric.report_pages fabric/power-bi/SupplyResponse.Report/definition --check
.venv/bin/python -m fabric.report_model fabric/power-bi/SupplyResponse.SemanticModel/definition fabric/reporting/queries --check
git diff --check
```
Do NOT run `test_power_bi_live.py`; its existing explicitly gated scenario mutates live state. The project suite must invoke the locked real Microsoft TOM parser, not a stub. If sandbox networking prevents NuGet restore, report the exact command for controller execution; do not weaken the gate or change package pins. TOM parses model structure and exact measure expressions but does not execute DAX or render visuals.

- [x] **Step 4: Commit only this task's files and write `.superpowers/sdd/report-artifact-integration-task-1-report.md` with RED/GREEN evidence, exact commands, commit, concerns and explicit unverified live-render/DAX gates.** Controller plans and unrelated files remain untouched.

## Complete integration code and test migrations

# Proposed generated report preflight integration

Design only. The snippets below replace the named definitions when `report_pages.py` and `report_model.py` are adopted together. Do not apply this to the existing two-page artifacts. The submitted PBIR/TMDL is never a source of expectations: expected documents, measures and partition queries come from checked-in Python generators and checked-in SQL under `fabric/reporting/queries`. An arbitrary caller-supplied manifest is not an authorization boundary; only the deployment entry point, which creates that manifest itself, is authoritative.

No schema catalog, lock file, package version, SDK import/auth gate, item identity, environment substitution, or publication-order changes are needed. Keep `_validate_offline_json_schemas`, `_validate_item_references`, `_discover_publish_items`, `_staged_repository`, `_preflight_substitution`, `_publish`, and `main` intact except for the explicitly listed calls. Keep the official locked restore/build/run sequence and its current diagnostic handling. This note does not execute DAX or authorize publication.

## `fabric/deploy.py`

Add these imports/constants. Script execution has to work as well as package import; the existing public entry is `python fabric/deploy.py`.

```python
if __package__ in (None, ""):
    import report_model
    import report_pages
else:
    from fabric import report_model, report_pages

REPORT_QUERIES = Path(__file__).resolve().parent / "reporting" / "queries"
EXPECTED_PAGE_ORDER = report_pages.ORDER
EXPECTED_EXPRESSIONS = (
    'expression FABRIC_SQL_SERVER = "__FABRIC_SQL_SERVER__" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\n'
    'expression FABRIC_SQL_DATABASE = "__FABRIC_SQL_DATABASE__" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
)
```

Delete the old `EXPECTED_QUERY_REFS`, `_projection_contract`, `_filter_contract` and `EXPECTED_VISUALS` blocks. Keep `EXPECTED_PLATFORM` and `EXPECTED_PUBLISH_ITEMS` verbatim. After the existing `_query_refs` definition add:

```python
EXPECTED_QUERY_REFS = {
    page: {
        ref
        for name, value in report_pages.artifacts().items()
        if name.startswith(f"pages/{page}/visuals/")
        for ref in _query_refs(value)
    }
    for page in EXPECTED_PAGE_ORDER
}
```

Replace `_validate_visual_inventory`; the old strict projection/filter parser helpers can remain for compatibility but are no longer the trust boundary. Exact generated document equality also covers new textbox, slicer and measure-filter shapes; it does not allow arbitrary versions of those shapes.

```python
def _validate_visual_inventory(report_definition: Path) -> None:
    try:
        report_pages.verify(report_definition)
    except (ValueError, OSError) as error:
        # Preserve useful visual/inventory diagnostics for existing adversarial tests.
        raise PreflightError(f"visual inventory or visual contract/filter drift: {error}") from error


def _validate_generated_model(semantic_definition: Path) -> None:
    try:
        # Check the entire folder before any parser follows a source path.
        if semantic_definition.is_symlink():
            raise ValueError("semantic definition must not be a symbolic link")
        paths = list(semantic_definition.rglob("*"))
        if any(path.is_symlink() for path in paths):
            raise ValueError("semantic artifacts must not contain symbolic links")
        generated = report_model.artifacts(REPORT_QUERIES)
        expected_files = set(generated) | {"expressions.tmdl"}
        actual_files = {
            path.relative_to(semantic_definition).as_posix()
            for path in paths if path.is_file()
        }
        if actual_files != expected_files:
            raise ValueError("unexpected semantic definition file inventory")
        actual_dirs = {
            path.relative_to(semantic_definition).as_posix()
            for path in paths if path.is_dir()
        }
        if actual_dirs != {"tables"}:
            raise ValueError("unexpected semantic definition directory inventory")
        if (semantic_definition / "expressions.tmdl").read_text(encoding="utf-8") != EXPECTED_EXPRESSIONS:
            raise ValueError("deployment expressions differ from approved parameters")
        report_model.check_required_fields(report_pages.required_fields())
        report_model.verify(semantic_definition, REPORT_QUERIES)
    except (ValueError, OSError) as error:
        raise PreflightError(f"generated semantic model contract: {error}") from error


def _tom_manifest() -> dict[str, Any]:
    # No reads from POWER_BI or the candidate semantic_definition here.
    contract = report_model.manifest()
    for name, table in contract["tables"].items():
        query = (REPORT_QUERIES / f"{name}.sql").read_text(encoding="utf-8")
        table["source"] = (
            "Sql.Database(FABRIC_SQL_SERVER, FABRIC_SQL_DATABASE, [Query="
            + report_model.m_string(query) + "])"
        )
        table["columns"] = {
            column: {"data_type": kind, "source_column": column,
                     "format_string": report_model.column_format(name, column) or "",
                     "hidden": False, "summarize_by": "none"}
            for column, kind in table["columns"].items()
        }
    return contract
```

In `_validate_project`, add all five generated `tables/<name>.tmdl` paths to `required`, replacing the old two explicit entries with `*(semantic_definition / "tables" / f"{name}.tmdl" for name in report_model.TABLES),`. Replace the page-order diagnostic with `report page order must contain exactly the eight approved pages`. Keep all existing size, refresh, query-ref, landing-page and page-directory checks. Replace its final `tmdl = ...` block with:

```python
    _validate_generated_model(semantic_definition)
    expressions = (semantic_definition / "expressions.tmdl").read_text(encoding="utf-8")
    if "__FABRIC_SQL_SERVER__" not in expressions or "__FABRIC_SQL_DATABASE__" not in expressions:
        raise PreflightError("semantic model deployment placeholders are missing")
```

At the start of `_validate_tmdl`, call `_validate_generated_model(semantic_definition)` before testing the `dotnet` executable. Inside its existing temporary directory, before `commands = (...)`, insert:

```python
        manifest_path = Path(dotnet_home) / "expected-model.json"
        manifest_path.write_text(json.dumps(_tom_manifest(), ensure_ascii=False), encoding="utf-8")
```

Append `"--manifest", str(manifest_path)` immediately after `str(semantic_definition)` in the existing run command. Do not modify restore/build flags, timeouts or error handling. In `_validate_staged_repository`, insert `_validate_generated_model(repository / "SupplyResponse.SemanticModel" / "definition")` immediately after `_validate_visual_inventory(...)` and before `_discover_publish_items`. This ensures a schema-valid model mutation fails even if a test stubs TOM, and before SDK discovery. The public main already calls `_validate_project` before staging and `_publish`; retain that sequence.

`expressions.tmdl` inventory and exact original text are retained above. This repository has no `database.tmdl`; do not require one. SQL Server/database replacement continues exclusively through the existing `parameter.yml` rules against `expressions.tmdl`. Partition SQL includes expression identifiers, never substituted credentials or endpoints. Preflight checks the original placeholder file before `fabric-cicd` applies the existing parameter rules; it does not validate a substituted model against the placeholder contract.

## TOM manifest branch

Add `using System.Text.Json;` and the code below to `tests/fabric/tmdl-validator/Program.cs`, placing this branch BEFORE the existing `if (args.Length != 1)`. Keep the existing one-argument branch unchanged until the combined integration lands. This lets the old report continue using its old contract in the interim; deployment of the new report ALWAYS uses the manifest branch. After adoption the default may be retired separately.

```csharp
if (args.Length == 3 && args[1] == "--manifest")
{
    try
    {
        using var document = JsonDocument.Parse(File.ReadAllText(args[2]));
        var root = document.RootElement;
        var expected = root.GetProperty("tables");
        var model = TmdlSerializer.DeserializeDatabaseFromFolder(args[0]).Model;
        static void Require(bool condition, string message)
        {
            if (!condition) throw new InvalidDataException(message);
        }
        static string Normalize(string value) => string.Join("\n",
            value.Replace("\r\n", "\n").Trim().Split('\n').Select(line => line.Trim()));
        static bool SameNames(IEnumerable<string> actual, IEnumerable<string> expected) =>
            actual.ToHashSet(StringComparer.Ordinal).SetEquals(expected);
        static DataType ExpectedType(string value) => value switch
        {
            "string" => DataType.String,
            "int64" => DataType.Int64,
            "double" => DataType.Double,
            "decimal" => DataType.Decimal,
            "boolean" => DataType.Boolean,
            "dateTime" => DataType.DateTime,
            _ => throw new InvalidDataException($"unsupported type {value}")
        };
        Require(expected.EnumerateObject().Count() == 5, "manifest must contain five tables");
        Require(SameNames(model.Tables.Select(t => t.Name),
            expected.EnumerateObject().Select(t => t.Name)), "unexpected TMDL tables");
        Require(root.GetProperty("relationships").GetArrayLength() == 0 && model.Relationships.Count == 0,
            "relationships are forbidden");
        foreach (var expectedTable in expected.EnumerateObject())
        {
            var table = model.Tables[expectedTable.Name];
            var spec = expectedTable.Value;
            Require(!table.IsHidden, $"{table.Name}: hidden table");
            var columns = spec.GetProperty("columns");
            Require(SameNames(table.Columns.Select(c => c.Name), columns.EnumerateObject().Select(c => c.Name)),
                $"{table.Name}: unexpected columns");
            foreach (var expectedColumn in columns.EnumerateObject())
            {
                var column = table.Columns[expectedColumn.Name];
                var c = expectedColumn.Value;
                Require(column is DataColumn, $"{table.Name}.{column.Name}: expected data column");
                Require(column.DataType == ExpectedType(c.GetProperty("data_type").GetString()!),
                    $"{table.Name}.{column.Name}: data type drift");
                Require(((DataColumn)column).SourceColumn == c.GetProperty("source_column").GetString(),
                    $"{table.Name}.{column.Name}: source column drift");
                Require((column.FormatString ?? "") == c.GetProperty("format_string").GetString()
                    && column.IsHidden == c.GetProperty("hidden").GetBoolean()
                    && column.SummarizeBy == AggregateFunction.None,
                    $"{table.Name}.{column.Name}: presentation drift");
            }
            Require(spec.GetProperty("mode").GetString() == "directQuery"
                && table.Partitions.Count == 1, $"{table.Name}: unexpected partitions");
            var partition = table.Partitions[0];
            Require(partition.Name == spec.GetProperty("partition").GetString()
                && partition.Mode == ModeType.DirectQuery && partition.Source is MPartitionSource,
                $"{table.Name}: partition contract drift");
            Require(Normalize(((MPartitionSource)partition.Source).Expression)
                == Normalize(spec.GetProperty("source").GetString()!), $"{table.Name}: source drift");
            var measures = spec.GetProperty("measures");
            Require(SameNames(table.Measures.Select(m => m.Name), measures.EnumerateObject().Select(m => m.Name)),
                $"{table.Name}: unexpected measures");
            foreach (var expectedMeasure in measures.EnumerateObject())
            {
                var measure = table.Measures[expectedMeasure.Name];
                var m = expectedMeasure.Value;
                Require(Normalize(measure.Expression) == Normalize(m.GetProperty("expression").GetString()!),
                    $"{table.Name}.{measure.Name}: expression drift");
                Require((measure.FormatString ?? "") == (m.GetProperty("format_string").GetString() ?? "")
                    && measure.IsHidden == m.GetProperty("hidden").GetBoolean(),
                    $"{table.Name}.{measure.Name}: presentation drift");
                // TOM deserialization does not infer/execute DAX result types. Validate the
                // declared manifest type vocabulary, but do not claim an engine result.
                _ = ExpectedType(m.GetProperty("result_type").GetString()!);
            }
        }
        Console.WriteLine("TMDL deserialized successfully with exact generated model contract; DAX was not executed.");
        return 0;
    }
    catch (Exception error)
    {
        Console.Error.WriteLine($"generated model contract failed: {error.Message}");
        return 1;
    }
}
```

Offline TOM cannot infer measure result types without engine evaluation. The exact declared column types are checked here; measure expression/format/visibility are checked exactly. The manifest's `result_type` is a declared interface for the independent executed-DAX gate. Do not compare TOM's unprocessed `Measure.DataType` to that declaration and call that a successful DAX type test. If a material requirement is offline persistence of measure type metadata, explicitly add a generator annotation and test that annotation; this is a generator expansion, not engine validation.

## `tests/fabric/test_power_bi_project.py`

Keep schema roots/hashes/reference-closure and malicious catalog tests, .platform stable UUID tests, discovery/publish ordering tests, parameter substitution, clean locked TOM build, dry run, SDK import order and partial-environment tests unchanged. Keep the numeric `FROZEN_OBSERVATIONS` corpus unchanged. Replace only assertions whose required behavior intentionally changes. These are test migrations, not skips: obsolete latest-showcase auto-selection becomes explicit external-case selection; old physical relationship becomes deliberately disconnected tables plus guarded DAX; old counting card becomes the approved answer card.

Add `from copy import deepcopy`, `from decimal import InvalidOperation`, `from fabric import report_model, report_pages`. Replace `PAGES`, `EXPECTED_VISUAL_IDS`, `QUERY_REF_ALLOWLIST` with the following block after `_query_refs` is defined (before any test runs):

```python
APPROVED_REPORT = report_pages.artifacts()
PAGES = {page: APPROVED_REPORT[f"pages/{page}/page.json"]["displayName"]
         for page in report_pages.ORDER}
EXPECTED_VISUAL_IDS = {
    page: tuple(sorted(Path(name).parent.name for name in APPROVED_REPORT
                       if name.startswith(f"pages/{page}/visuals/"))) for page in PAGES
}
QUERY_REF_ALLOWLIST = {
    page: {ref for name, value in APPROVED_REPORT.items()
           if name.startswith(f"pages/{page}/visuals/") for ref in _query_refs(value)}
    for page in PAGES
}
```

In `test_required_power_bi_artifacts_exist`, replace the two explicit table paths with `*(SEMANTIC_MODEL / "tables" / f"{table}.tmdl" for table in report_model.TABLES),`.

Rename `test_power_bi_project_has_only_the_two_required_pages` to `test_power_bi_project_has_exactly_eight_generated_pages`, retaining its body and adding `assert len(PAGES) == 8`. In `test_every_visual_is_schema_shaped_and_inside_its_page`, add `syncGroup` to the allowed visual keys. Immediately before the `query_state` lookup, add `if visual_container["visual"]["visualType"] == "textbox": assert "query" not in visual_container["visual"]; continue` (use ordinary multiline formatting). All non-textbox field/query-shape checks remain.

Replace `test_preflight_has_exact_visual_inventory_and_per_visual_contracts` with:

```python
def test_preflight_has_exact_visual_inventory_and_per_visual_contracts() -> None:
    from fabric import deploy
    assert deploy.EXPECTED_PAGE_ORDER == report_pages.ORDER
    assert deploy.EXPECTED_QUERY_REFS == QUERY_REF_ALLOWLIST
    deploy._validate_visual_inventory(REPORT)
    old_ids = {
        "command-center": {"active-cases", "current-decision", "otif-loss", "revenue-at-risk", "scenario-effective-time", "showcase-cases"},
        "actions-outcomes": {"action-status", "decision-id", "observation-kind", "predicted-observed-variance", "projection-refresh", "scenario-effective-time"},
    }
    for page, names in old_ids.items():
        assert names <= set(EXPECTED_VISUAL_IDS[page])
```

Keep all existing visual inventory attack tests. Rename “thirteenth” to “additional” in the extra-visual test. The existing `action-status` remains a gated action table. Update `_mutate_aggregation_function` to wrap the card's field rather than indexing a removed aggregate:

```python
def _mutate_aggregation_function(value: dict[str, Any]) -> None:
    p = value["visual"]["query"]["queryState"]["Data"]["projections"][0]
    p["field"] = {"Aggregation": {"Expression": {
        "Column": {"Expression": {"SourceRef": {"Entity": "CaseCommandCenter"}},
                   "Property": "case_id"}}, "Function": 0}}

def _mutate_filter_type(value: dict[str, Any]) -> None:
    value["filterConfig"]["filters"][0]["type"] = "Categorical"
```

In `test_visual_inventory_rejects_wrong_page_and_altered_locked_filter`, replace the `In/Values` mutation with:

```python
    comparison = visual["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"]["Comparison"]
    comparison["Right"]["Literal"]["Value"] = "0L"
```

All eight schema-valid mutation parameters and their schema-validation assertion remain. Add the following independent cases to protect source aliases, gate locking and synchronized selection (the first three modify supporting-records; the latter two modify the case-selector):

```python
@pytest.mark.parametrize("attack", ["unlock", "remove-gate", "alias", "picker-sync", "picker-field"])
def test_scope_mutations_fail_before_auth(tmp_path, monkeypatch, attack):
    from fabric import deploy
    repository = _staged_visual_mutation_repository(tmp_path, attack)
    page = "supplier-shipment"
    visual = "case-selector" if attack.startswith("picker-") else "supporting-records"
    path = _visual_path(repository, page, visual)
    value = _load(path)
    if attack == "unlock":
        value["filterConfig"]["filters"][0]["isLockedInViewMode"] = False
    elif attack == "remove-gate":
        del value["filterConfig"]
    elif attack == "alias":
        value["filterConfig"]["filters"][0]["filter"]["From"][0]["Name"] = "other"
    elif attack == "picker-sync":
        value["visual"]["syncGroup"]["filterChanges"] = False
    else:
        value["visual"]["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"]["Property"] = "status"
    path.write_text(json.dumps(value), encoding="utf-8")
    deploy._validate_offline_json_schemas(repository)
    monkeypatch.setattr(deploy, "POWER_BI", repository)
    monkeypatch.setattr(deploy, "_validate_python", lambda: None)
    monkeypatch.setattr(deploy, "_required_environment", lambda: VISUAL_PREFLIGHT_VALUES)
    monkeypatch.setattr(deploy, "_publish", lambda _: pytest.fail("publish/auth reached"))
    monkeypatch.setattr(deploy, "_discover_publish_items", lambda _: pytest.fail("SDK discovery reached"))
    monkeypatch.setattr(sys, "argv", ["deploy.py"])
    with pytest.raises(SystemExit):
        deploy.main()
```

Replace the obsolete five visual behavior functions (`test_showcase_table_binds_latest_case_and_showcase_filters`, `test_active_cases_card_counts_distinct_non_closed_cases`, `test_actions_page_binds_scenario_effective_time_card`, `test_action_and_observation_visuals_have_locked_record_type_scope`, `test_latest_showcase_decision_is_the_default_visual_context`) with these five behavioral tests:

```python
def test_case_picker_is_explicit_single_select_and_synced_on_every_page():
    for page in PAGES:
        v = _load(REPORT / "pages" / page / "visuals" / "case-selector" / "visual.json")["visual"]
        assert v["visualType"] == "slicer"
        assert v["syncGroup"] == {"groupName": "SupplyResponseCase", "fieldChanges": True, "filterChanges": True}
        assert v["objects"]["selection"][0]["properties"]["singleSelect"] == {"expr": {"Literal": {"Value": "true"}}}
        assert "general" not in v["objects"]
        assert v["query"]["queryState"]["Values"]["projections"][0]["queryRef"] == "CaseCommandCenter.case_id"

def test_overview_contains_nine_saved_answer_bindings():
    expected = {"Disruption", "Availability", "Exposure", "Shipment", "Transfer", "Qualification", "Options", "Recommendation", "Decision"}
    actual = {ref.removeprefix("CaseCommandCenter.").removesuffix(" Answer")
              for ref in QUERY_REF_ALLOWLIST["command-center"] if ref.endswith(" Answer")}
    assert actual == expected
    report_pages.verify(REPORT)

def test_actions_preserve_scenario_and_projection_context():
    refs = QUERY_REF_ALLOWLIST["actions-outcomes"]
    assert {"CaseCommandCenter.Scenario Context", "CaseCommandCenter.Projection Updated Display",
            "CaseCommandCenter.Current Decision Display"} <= refs
    report_pages.verify(REPORT)

def test_all_business_tables_and_variance_have_locked_scope_gates():
    for path in REPORT.glob("pages/*/visuals/*/visual.json"):
        value = _load(path)
        if value["visual"]["visualType"] not in {"tableEx", "clusteredColumnChart"}:
            continue
        gates = [f for f in value["filterConfig"]["filters"] if "Measure" in f["field"]]
        assert len(gates) == 1
        gate = gates[0]
        assert gate["isHiddenInViewMode"] and gate["isLockedInViewMode"]
        assert gate["field"]["Measure"]["Property"].endswith("Row Visible")
        assert gate["filter"]["Where"][0]["Condition"]["Comparison"]["Right"] == {"Literal": {"Value": "1L"}}
    chart = _load(REPORT / "pages/actions-outcomes/visuals/predicted-observed-variance/visual.json")
    assert set(_query_refs(chart)) >= {"ActionOutcomes.metric", "ActionOutcomes.observation_kind", "ActionOutcomes.Observed Variance"}

def test_no_persisted_case_default_or_latest_showcase_override():
    for page in PAGES:
        filters = _load(REPORT / "pages" / page / "page.json").get("filterConfig", {}).get("filters", [])
        assert all(f["field"].get("Column", {}).get("Property") == "record_family" for f in filters)
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    assert "Latest Showcase Case" not in definitions
    selector = definitions["External Selected Case Key"]["expression"]
    assert "ISFILTERED" in selector and "HASONEFILTER" in selector
    assert "COUNTROWS(CaseCommandCenter) == 1" in selector
    assert "ALLSELECTED" in definitions["Selected Case Key"]["expression"]
```

Replace the obsolete model test bodies with the following (rename the two latest-showcase/relationship test names as shown; retain the uniqueness test verbatim):

```python
def test_semantic_model_exposes_decision_and_simulation_measures():
    report_model.check_required_fields(report_pages.required_fields())
    report_model.verify(SEMANTIC_MODEL, ROOT / "fabric/reporting/queries")

def test_current_context_measures_are_scoped_to_explicit_case_and_decision():
    definitions = report_model.manifest()["tables"]["CaseCommandCenter"]["measures"]
    for name in ("Action Row Visible", "Observation Row Visible", "Current Actions Count", "Current Observations Count"):
        text = definitions[name]["expression"]
        assert "[Selected Case Key]" in text and "[Current Decision Key]" in text
        assert "KEEPFILTERS(TREATAS" in text
        assert "ISBLANK" in text

def test_tmdl_folder_has_strong_structural_contract():
    from fabric import deploy
    deploy._validate_generated_model(SEMANTIC_MODEL)
    assert len(report_model.manifest()["tables"]) == 5
    definitions = report_model.manifest()["tables"]
    expression = definitions["ActionOutcomes"]["measures"]["Observed Variance"]["expression"]
    assert "[Observation Row Visible] == 1" in expression
    assert "IFERROR(VALUE(PredictedText), BLANK())" in expression
    assert "IFERROR(VALUE(ObservedText), BLANK())" in expression
    assert "ABS(Predicted)" in expression and "Predicted == 0" in expression
    assert "AVERAGEX" not in expression and "ALL(ActionOutcomes)" not in expression
    assert '"remaining_alpha_recovery_date"' not in expression

def test_model_has_no_relationships_and_uses_guarded_decision_scope():
    assert (SEMANTIC_MODEL / "relationships.tmdl").read_text() == ""
    assert report_model.manifest()["relationships"] == []
    test_current_context_measures_are_scoped_to_explicit_case_and_decision()
```

Replace `test_tmdl_deserializes_with_microsoft_tom_parser` with a call to `deploy._validate_tmdl(SEMANTIC_MODEL)`; it now invokes the exact manifest contract and preserves the mandatory missing-dotnet failure. Retain the clean tracked copy test verbatim; its call obtains the new manifest automatically. Add the model adversarial suite:

```python
@pytest.mark.parametrize("attack", ["column-type", "column-source", "measure-expression", "measure-format", "measure-hidden", "partition-query", "relationship", "extra-table", "expression", "symlink"])
def test_model_mutations_fail_before_sdk_or_auth(tmp_path, monkeypatch, attack):
    from fabric import deploy
    repository = _staged_visual_mutation_repository(tmp_path, attack)
    definition = repository / "SupplyResponse.SemanticModel/definition"
    path = definition / "tables/ActionOutcomes.tmdl"
    text = path.read_text()
    replacements = {
        "column-type": ("dataType: string", "dataType: int64"),
        "column-source": ("sourceColumn: case_id", "sourceColumn: decision_id"),
        "measure-expression": ("ABS(Predicted)", "Predicted"),
        "measure-format": ("0.00%;-0.00%;0.00%", "0.00"),
        "measure-hidden": ("    formatString:", "    isHidden\n    formatString:"),
        "partition-query": ("Sql.Database(", "Sql.Databases("),
    }
    if attack in replacements:
        old, new = replacements[attack]
        assert old in text
        path.write_text(text.replace(old, new, 1))
    elif attack == "relationship":
        (definition / "relationships.tmdl").write_text("relationship Unexpected\n  fromColumn: ActionOutcomes.case_key\n  toColumn: CaseCommandCenter.case_key\n")
    elif attack == "extra-table":
        (definition / "tables/Extra.tmdl").write_text("table Extra\n")
    elif attack == "expression":
        (definition / "expressions.tmdl").write_text(deploy.EXPECTED_EXPRESSIONS + '\nexpression Extra = "unexpected"\n')
    else:
        outside = tmp_path / "external.tmdl"
        outside.write_text(text)
        path.unlink()
        path.symlink_to(outside)
    monkeypatch.setattr(deploy, "_discover_publish_items", lambda _: pytest.fail("SDK discovery reached"))
    monkeypatch.setattr(deploy, "_validate_tmdl", lambda _: pytest.fail("parser reached before generated contract"))
    with pytest.raises(deploy.PreflightError, match="semantic model contract"):
        deploy._validate_staged_repository(repository, VISUAL_PREFLIGHT_VALUES)
```

Harden the numeric oracle instead of removing it. Replace its body with:

```python
    if metric not in SUPPORTED_VARIANCE_METRICS:
        return None
    try:
        baseline, actual = Decimal(predicted), Decimal(observed)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not baseline.is_finite() or not actual.is_finite() or baseline == 0:
        return None
    return (actual - baseline) / abs(baseline)
```

Add:

```python
@pytest.mark.parametrize("predicted,observed", [("unknown", "10"), ("10", "unknown"), ("NaN", "1"), ("1", "Infinity"), ("", "1")])
def test_variance_oracle_rejects_non_numeric_and_non_finite_values(predicted, observed):
    assert _relative_variance_oracle("response_cost", predicted, observed) is None

def test_variance_oracle_preserves_observed_zero_and_negative_baseline():
    assert _relative_variance_oracle("response_cost", "10", "0") == Decimal("-1")
    assert _relative_variance_oracle("response_cost", "-10", "-5") == Decimal("0.5")
```

The existing live-contract static test at the end references obsolete DAX measures in `tests/fabric/test_power_bi_live.py`. This is unavoidable expansion: migrate its query strings with the concrete change below, preserving the existing setup workflow, deadlines, API result checks, credential/configuration gates and all final assertions. No live calls are performed by writing or reviewing this design. The existing test creates a showcase case/analysis/decision/playback when explicitly enabled; do not execute it as an offline verification step.

Add this helper to that file:

```python
def _dax_literal(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
```

Rename its test to `test_selected_case_decision_reaches_power_bi_within_sixty_seconds`. Replace the `dax = ...` and `variance_dax = ...` assignments with:

```python
    selected_case = _dax_literal(case["case_id"])
    selected_decision = _dax_literal(decision["decision_id"])
    dax = f'''EVALUATE
CALCULATETABLE(
  ROW(
    "case_id", SELECTEDVALUE(CaseCommandCenter[case_id]),
    "decision_id", SELECTEDVALUE(ActionOutcomes[decision_id]),
    "current_decision_id", CaseCommandCenter[Current Decision ID],
    "selected_option_id", SELECTEDVALUE(ActionOutcomes[selected_option_id]),
    "action_count", CaseCommandCenter[Current Actions Count],
    "action_completion", DIVIDE(
        CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[record_type] = "action", ActionOutcomes[action_status] = "completed"),
        CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[record_type] = "action")),
    "simulated_observation_count", CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[record_type] = "observation", ActionOutcomes[observation_kind] = "simulated"),
    "observation_kind", CaseCommandCenter[Current Observation Kind],
    "scenario_effective_time", MAX(ActionOutcomes[scenario_effective_time]),
    "projection_refresh_time", CaseCommandCenter[Projection Refresh Time]
  ),
  TREATAS({{{selected_case}}}, CaseCommandCenter[case_id]),
  TREATAS({{{selected_case}}}, ActionOutcomes[case_id]),
  TREATAS({{{selected_decision}}}, ActionOutcomes[decision_id])
)'''
    variance_dax = f'''EVALUATE
CALCULATETABLE(
  UNION(
    ROW("metric", "response_cost", "relative_variance", CALCULATE(
      ActionOutcomes[Observed Variance],
      ActionOutcomes[record_type] = "observation",
      ActionOutcomes[observation_kind] = "simulated",
      ActionOutcomes[metric] = "response_cost")),
    ROW("metric", "remaining_alpha_recovery_date", "relative_variance", CALCULATE(
      ActionOutcomes[Observed Variance],
      ActionOutcomes[record_type] = "observation",
      ActionOutcomes[observation_kind] = "simulated",
      ActionOutcomes[metric] = "remaining_alpha_recovery_date"))
  ),
  TREATAS({{{selected_case}}}, CaseCommandCenter[case_id]),
  TREATAS({{{selected_case}}}, ActionOutcomes[case_id]),
  TREATAS({{{selected_decision}}}, ActionOutcomes[decision_id])
)'''
```

In `test_live_contract_queries_required_measures_and_variance_contexts`, change the required tuple to the following and retain its loop plus the two simulated-variance assertions:

```python
    for required in (
        "CaseCommandCenter[Current Decision ID]",
        "CaseCommandCenter[Current Actions Count]",
        "ActionOutcomes[Observed Variance]",
        "MAX(ActionOutcomes[scenario_effective_time])",
        "CaseCommandCenter[Projection Refresh Time]",
        'ActionOutcomes[metric] = "response_cost"',
        'ActionOutcomes[metric] = "remaining_alpha_recovery_date"',
        "TREATAS({{{selected_case}}}, CaseCommandCenter[case_id])",
        "TREATAS({{{selected_decision}}}, ActionOutcomes[decision_id])",
    ):
        assert required in live_test
```

This migrates the existing live smoke test without dropping its checks. It does not claim complete grouped-DAX, slicer-sync or visual-render acceptance. The separate multi-case/analysis/record/grouped-visual engine acceptance described in the generator design remains a release gate; offline TOM or this smoke test cannot prove it.

Before applying: evaluate these proposed tests against the latest generator names (agents may polish copy but binding/interface changes require explicit reconciliation), compile the generated Python modules, run vendored schema checks, then the existing locked TOM gate without changing package pins. Review TOM parser formatting normalization against actual output. All 18 proposed Python blocks were parsed with Python's AST parser (indented fragments parsed as function bodies); none were executed. No .NET compiler or engine has been invoked for this design note.

## Complete replacement README.md

```markdown
# Supply Response Power BI reports

The native report follows the same saved case and analysis as the planner workspace. It presents the supplier delay first, then available stock and customer orders, response choices, and the recorded decision. Focused pages expose the exact saved shipment, transfer or qualification record behind a card.

All scenario data is fictional. A saved analysis is historical evidence, not a fresh source retrieval. Missing or incomplete records display as unavailable; recommendations and approved decisions remain separate. Simulated observations stay labeled as simulated.

## Build and verify locally

From the repository root:

```sh
.venv/bin/python -m fabric.report_pages fabric/power-bi/SupplyResponse.Report/definition
.venv/bin/python -m fabric.report_model fabric/power-bi/SupplyResponse.SemanticModel/definition fabric/reporting/queries
.venv/bin/pytest tests/fabric/test_report_generators.py tests/fabric/test_power_bi_project.py tests/fabric/test_schema_updater.py -o addopts='' -q
```

The generators own the checked-in PBIR pages and TMDL tables. Edit the generator and its tests, then regenerate; do not hand-edit generated artifacts. Deployment preflight checks exact generated content, the pinned Microsoft schema catalog, stable item identities and Microsoft's locked TOM parser before publication can begin.

The five DirectQuery projections read saved reporting views in the existing Fabric SQL database. They do not create another production database. Case, analysis and record selection use explicit scoped measures; page URL filters are navigation context, not an authorization boundary.

## Acceptance and release

Passing local checks establishes artifact structure and source/query contracts. It does **not** prove DAX engine results, native visual rendering, report access or link navigation.

Before activating the new card links, the coordinated release must verify the saved views in Fabric, publish the matching model/report, execute read-only multi-case and historical-analysis checks, and inspect each page in native Power BI. The API must expose the matching reporting contract only after those gates pass. The traditional dashboard walkthrough is a separate delivery stage.

This folder does not authorize deployment or new live scenario runs. Use the repository's approval-gated deployment workflow when release is explicitly authorized.

```

## Actual SQL-to-model column verification (controller-owned execution)

Add the following verification test to `tests/integrations/test_saved_analysis_reporting_sql.py`.
This extra file is in scope because the generated model must agree with the actual
SQL result columns/types, not just another copied manifest. Do not change SQL or
model semantics to make it pass without controller review. The controller runs
this existing disposable SQL fixture on the dedicated private test VM; never treat
the local skip as a pass.

```python
@pytest.mark.parametrize("table_name", [
    "CaseCommandCenter", "ActionOutcomes", "SavedAnalyses", "SavedRecords", "SavedOptions",
])
def test_report_partition_matches_declared_model_columns_and_types(engine, table_name):
    from pathlib import Path

    from fabric.report_model import TYPES

    query = (
        Path(__file__).resolve().parents[2]
        / "fabric/reporting/queries"
        / f"{table_name}.sql"
    ).read_text(encoding="utf-8")
    metadata = rows(
        engine,
        "SELECT name, system_type_name, error_number, error_message "
        "FROM sys.dm_exec_describe_first_result_set(:sql_text, NULL, 0) "
        "WHERE is_hidden=0 OR error_number IS NOT NULL ORDER BY column_ordinal",
        sql_text=query,
    )
    assert metadata and all(row["error_number"] is None for row in metadata), metadata
    assert [row["name"] for row in metadata] == list(TYPES[table_name])
    allowed = {
        "string": {"nvarchar", "varchar", "nchar", "char"},
        "int64": {"bigint", "int", "smallint", "tinyint"},
        "decimal": {"decimal", "numeric", "money", "smallmoney"},
        "boolean": {"bit"},
        "dateTime": {"date", "datetime", "datetime2", "smalldatetime"},
        "double": {"float", "real"},
    }
    for row in metadata:
        sql_type = row["system_type_name"].split("(", 1)[0]
        assert sql_type in allowed[TYPES[table_name][row["name"]]], dict(row)
```

Notify controller to upload this test file plus `fabric/report_model.py` and run
the existing guarded SQL runner against the complete reporting/script suite
(expected count126). Do not commit this task before the actual SQL check passes.
No third-party data or credentials are sent; only user-project test/model code
goes to the already verified private test VM. Add this file to Ruff and the
task's scoped commit. This is a new verification test, not a claim of a SQL bug;
canonical GREEN is acceptable, with actual metadata checked for every column.
