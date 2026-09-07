# Work IQ Response-Shape Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inspect failed Work IQ response structure without disclosing content.

**Architecture:** Add a bounded structure-only summarizer and a failure-only hook
around the existing normalizer. Keep parsing and evidence acceptance unchanged.
The controller owns Azure validation, deployment and the one-attempt observation.

**Tech Stack:** Existing Python 3.12+, pytest, standard-library logging and JSON.

## Global Constraints

- Work directly on `main`; do not push.
- No primitive values, string lengths, unknown field names, text, IDs, URLs,
  timestamps, headers, prompts, tokens or exceptions in diagnostic output.
- At most 128 visited nodes, 12 levels, two array/unknown-key examples per
  container, 8,192 serialized characters and one record per source kind per process.
- No changes to requests, authentication, normalizer decisions, evidence policy,
  public errors, billing, roles, source data, dependencies or infrastructure.
- Remove the hook after capture and mapping verification; no raw payload storage.

### Task 1: Failure-only structural diagnostic

**Files:**
- Create: `integrations/workiq/diagnostics.py`
- Modify: `integrations/workiq/normalizer.py`
- Create: `tests/integration/test_workiq_response_shape_diagnostics.py`

**Interfaces:**
- Consumes: the existing validated A2A payload and expected authority scope.
- Produces: `response_shape(payload: object) -> str`, and
  `log_response_shape(payload: object, source_kind: str) -> None`.
- Rename the existing normalization implementation to `_normalize_a2a_evidence`;
  retain the exact public `normalize_a2a_evidence` signature in a wrapper that calls
  it, logs a bounded diagnostic on `Exception`, and re-raises the original error.
  Derive source kind from exact enum identity: supplier, quality, or other.

- [ ] Write tests first using the real normalizer and public diagnostic helpers.
  Required examples include secret values/keys, nested reference maps, all JSON
  scalar types, cyclic/deep/wide inputs, JSON-looking text, both real fixture
  normalizations succeeding without logs, malformed data still raising its
  original error, and repeated same-source failures producing one record.

```python
def test_shape_never_copies_scalar_values():
    from integrations.workiq.diagnostics import response_shape
    result = response_shape({"text": "secret-value", "secret-key": {"url": "secret-url"}})
    assert "secret" not in result
    assert '"text"' in result
    assert '"string"' in result
```

- [ ] Run `.venv/bin/pytest -q tests/integration/test_workiq_response_shape_diagnostics.py`
  before implementation; record the expected missing-diagnostic failure.
- [ ] Implement the summarizer by recursively constructing a new JSON tree:
  scalar leaves are fixed labels (`string`, `number`, `boolean`, `null`, `other`);
  objects contain `type`, `count`, allowlisted `fields` and at most two `unknown`
  child shapes; arrays contain `type`, `count`, at most two `items` and truncation.
  Use a shared node budget and depth limit before recursion. Serialize compactly;
  if longer than 8,192 characters return `{"type":"truncated"}` instead.
  Approved keys are exactly: `result`, `task`, `id`, `contextId`, `status`, `state`,
  `message`, `artifacts`, `artifactId`, `name`, `description`, `parts`, `text`,
  `data`, `metadata`, `mediaType`, `url`, `raw`, `filename`, `facts`, `factId`,
  `claim`, `sourceTimestamp`, `effectiveAt`, `expiresAt`, `authorityScope`,
  `citation`, `citations`, `citationMap`, `references`, `reference`, `sources`,
  `source`, `sourceId`, `sourceType`, `excerpt`, `targetLink`, `webUrl`,
  `isCitedInResponse`, `content`, `type`, `value`, `index`, `title`.
  Unknown keys are never emitted, including within nested metadata.
- [ ] Hook the public normalizer without changing its decisions:

```python
try:
    return _normalize_a2a_evidence(payload, **existing_named_arguments)
except Exception:
    log_response_shape(payload, source_kind)
    raise
```

  Preserve all existing named arguments explicitly in production code. The logger
  only accepts exact fixed source labels; unknown input becomes `other`. Keep a
  module-private set of emitted source labels. Add to the set before emitting one
  warning: `workiq_response_shape source=%s shape=%s`. Only sanitized strings may
  enter logging arguments; no `exc_info` or `stack_info`. Diagnostic failures must
  not mask the original normalization error.
- [ ] Run the new tests and Work IQ contract/trust/HTTP/OBО diagnostic tests. Run
  scoped Ruff and Pyright. Commit only these three files, with TDD evidence and
  self-review in the requested ignored report file.
- [ ] Independent task and whole-change review must approve before deployment.

### Controller verification and observation

- [ ] Run full `uv run pytest -q`, `uv build`, and web tests/production build.
- [ ] Complete fresh azure-validate workflow with actual evidence, then run the
  existing `scripts/deploy_personal_tenant.sh --apply` and `--smoke` via azure-deploy.
- [ ] Verify new revision health, 100% traffic, unchanged identity/roles and URL.
- [ ] Use one authenticated Alex analysis attempt and read only structural logs.
- [ ] Record exact observations locally. Do not claim the mapping or analysis
  fixed until a subsequent faithful-contract correction passes live acceptance.
