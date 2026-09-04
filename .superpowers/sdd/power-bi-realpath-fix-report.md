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
  - proves the real local `fabric-cicd` report processor raises
    `ItemDependencyError` for the unresolved alias; and
  - captures `_publish()` to assert it passes the resolved repository path,
    preserves `SemanticModel` then `Report`, and uses a synthetic credential.

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
run. The focused test exercises the actual local `fabric-cicd` report dependency
lookup and the publication-boundary path argument.

## Commit

- Branch: `main` (recorded in Git history with this fix)
