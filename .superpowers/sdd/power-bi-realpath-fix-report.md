# Power BI Staged Repository Realpath Fix Report

## Status

The staged Power BI repository is canonicalized with `Path.resolve()` before
being passed to `fabric_cicd.FabricWorkspace`. The checked-in PBIR
`datasetReference.byPath` remains unchanged. This report is updated during the
final takeover verification and is committed with the fix.

## Files changed

- `fabric/deploy.py` resolves the return value of `_staged_repository(...)` in
  `_publish()` before `FabricWorkspace` construction.
- `tests/fabric/test_power_bi_project.py` adds a regression test which:
  - stages a repository below a symlinked temporary prefix;
  - captures `_publish()` to assert it passes the resolved repository path,
    preserves `SemanticModel` then `Report`, and uses a synthetic credential.
- `tests/fabric/test_fabric_cicd_1_3_0_path_compatibility.py` contains the
  version-pinned upstream compatibility proof that the real local
  `fabric-cicd` report processor raises `ItemDependencyError` for the
  unresolved alias.

No report or semantic-model content, IDs, database/schema values, or deployment
parameters changed. The test does not authenticate or make Fabric calls.

## TDD evidence recorded at handoff

The pre-existing handoff record documented the focused regression test failing
before the one-line production change because `_publish()` supplied the aliased
path, then passing after the change. This takeover did not reconstruct that
historical RED state by reverting production code; it independently verified
the current GREEN state below.

## Fresh verification (takeover)

```text
uv run pytest tests/fabric/test_power_bi_project.py::test_publish_resolves_aliased_staged_repository_for_report_dependency -q
.                                                                        [100%]
```

```text
uv run ruff check fabric/deploy.py tests/fabric/test_power_bi_project.py
All checks passed!
```

```text
git diff --check
```

Exit code `0`.

Per takeover direction, no full suite, Power BI dry-run, or cloud command was
run. The focused project test verifies the publication-boundary path argument.
The separate version-pinned compatibility test verifies the real local
`fabric-cicd` report dependency lookup.

## Commit

- Branch: `main` (recorded in Git history with this fix)

## Compatibility-test isolation follow-up

The upstream private-API reproduction now lives in
`tests/fabric/test_fabric_cicd_1_3_0_path_compatibility.py`, whose module name,
docstring, test name, and version assertion explicitly pin it to
`fabric-cicd 1.3.0`. The ordinary project test retains only the local
`_publish()` boundary assertion: it uses local fake import modules, a synthetic
credential, and a symlinked temporary directory without importing or calling
`fabric_cicd` internals.

Verification:

```text
uv run pytest tests/fabric/test_power_bi_project.py::test_publish_resolves_aliased_staged_repository_for_report_dependency tests/fabric/test_fabric_cicd_1_3_0_path_compatibility.py::test_fabric_cicd_1_3_0_rejects_aliased_repository_report_dependency -q
..                                                                       [100%]
```

```text
uv run pytest tests/fabric/test_power_bi_project.py -q
...........................................................
```

The bounded project file exited `0`.

```text
uv run ruff check fabric/deploy.py tests/fabric/test_power_bi_project.py tests/fabric/test_fabric_cicd_1_3_0_path_compatibility.py
All checks passed!
```

```text
git diff --check
```

Exit code `0`. No cloud command, authentication, or Fabric publication was run.
