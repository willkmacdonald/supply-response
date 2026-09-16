# Task 9 Graph capability stage diagnostic report

## Status

DONE

## Implemented scope

- Added one privacy-safe warning on a failed `GraphMailClient.capability` call through logger `supply_response.graph_mail`.
- Limited diagnostic stages to `sent_list_obo`, `sent_list_http`, `sent_list_shape`, `exact_get_obo`, `exact_get_http`, `exact_get_shape`, and `sender_binding`.
- Limited diagnostic outcomes to `timeout`, `transport`, `non_success`, `invalid_shape`, and `mismatch`.
- Preserved the two separate OBO exchanges already performed by the two Graph requests.
- Kept the public 503 response, Graph request shapes, timeouts, permissions, and send-disabled behavior unchanged.
- Added redaction coverage for tokens, provider details, URLs/query strings, identifiers, addresses, sender/recipient data, subjects, bodies, and actor identifiers.
- Made no cloud calls, deployments, mailbox accesses, permission changes, schema changes, UI changes, or email actions.

## TDD evidence

### RED

Command:

```text
uv run pytest tests/integration/test_graph_mail_capability_diagnostics.py tests/api/test_mail_capability.py
```

Observed result before production changes:

```text
8 failed, 6 passed, 1 warning
```

All eight new diagnostic cases failed because logger `supply_response.graph_mail` emitted zero records instead of the required one.

### GREEN

Command:

```text
uv run pytest tests/integration/test_graph_mail_capability_diagnostics.py tests/api/test_mail_capability.py
```

Observed result after the minimal production change:

```text
14 passed, 1 warning in 0.18s
```

## Verification

Focused Graph mail and API regression command:

```text
uv run pytest tests/integration/test_graph_mail.py tests/integration/test_graph_mail_capability_diagnostics.py tests/api
```

Result:

```text
105 passed, 1 warning in 13.44s
```

The warning is the existing Starlette deprecation warning from `fastapi.testclient`; there were no test failures.

Scoped Ruff command:

```text
uv run ruff check integrations/graph_mail/client.py tests/integration/test_graph_mail_capability_diagnostics.py tests/api/test_mail_capability.py
```

Result: all checks passed.

Scoped Pyright command:

```text
uv run pyright integrations/graph_mail/client.py tests/integration/test_graph_mail_capability_diagnostics.py tests/api/test_mail_capability.py
```

Result: 0 errors, 0 warnings, 0 informations.

## Follow-up: invalid content-encoding regression

A scoped review found that `httpx.DecodingError` from
`response.aiter_bytes()` was not a subclass of the already handled
`httpx.TransportError`. Invalid gzip bytes could therefore escape the
capability diagnostic without the required safe `GraphMailError` and warning.

The fix catches only `httpx.DecodingError`. Capability requests classify it as
the current request's shape stage with outcome `invalid_shape`; non-diagnostic
Graph requests re-raise it unchanged. No broad `httpx.RequestError` catch was
added.

### Follow-up RED

Command:

```text
uv run pytest tests/integration/test_graph_mail_capability_diagnostics.py::test_capability_decoding_error_is_a_bounded_shape_failure
```

Observed result before the production fix:

```text
1 failed in 0.17s
```

The 200 `application/json` response with `Content-Encoding: gzip` and invalid
gzip bytes raised `httpx.DecodingError` from `response.aiter_bytes()` instead of
the expected safe `GraphMailError`.

### Follow-up GREEN

The same command after the narrow catch:

```text
1 passed in 0.13s
```

### Follow-up verification

Focused Graph mail and API regression command:

```text
uv run pytest tests/integration/test_graph_mail.py tests/integration/test_graph_mail_capability_diagnostics.py tests/api
```

Result:

```text
106 passed, 1 warning in 13.35s
```

The warning remains the existing Starlette deprecation warning from
`fastapi.testclient`.

Scoped Ruff result: all checks passed.

Scoped Pyright result: 0 errors, 0 warnings, 0 informations.

## Files changed for this task

- `integrations/graph_mail/client.py`
- `tests/integration/test_graph_mail_capability_diagnostics.py`
- `tests/api/test_mail_capability.py`
- `.superpowers/sdd/execute-mitigation-task-9-graph-stage-diagnostic-report.md`

## Preserved unrelated work

- `.azure/deployment-plan.md` was already modified and was not edited or staged.
- `.pnpm-store/` was already untracked and was not edited or staged.

## Concerns

None. The existing Starlette deprecation warning remains unrelated to this task.
