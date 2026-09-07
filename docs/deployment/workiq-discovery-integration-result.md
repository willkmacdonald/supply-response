# Work IQ discovery/evidence integration — deployment and acceptance result

Verified 2026-09-07 UTC. This records deployment separately from live acceptance.

## Deployed and verified

- Implementation through `1f6afc3`, validation record `aa67991`, deployed through
  the approved existing-app workflow. No Git push.
- ACR build `ch14` succeeded. Immutable image digest:
  `5603a03bd1def6b52f692c252cf3344c63036cf8cc69b4cd222df59bfed4894d`.
- `ca-sr-demo--0000014` is the sole active/latest-ready revision, Healthy/Running,
  with 100% traffic. Scale remains 0–2; app identity and the exact registry,
  Key Vault and Foundry role assignments are unchanged.
- Read-only preflight, deployment preview (no new resources), package, live
  Fabric/Foundry readiness and public health (live/Fabric SQL/schema 12) passed.
- Full backend tests and frontend 51-test/build checks passed. After the final
  receipt-guard fix, 83 covering regressions and the package rebuild passed.
  Task and whole-change reviews found no remaining Critical/Important issues.

## Single normal Alex Analyze — failed

Alex's existing authenticated browser session loaded the deployed app, created
one live showcase Case, and invoked Analyze once at approximately 23:40 UTC.
The normal UI returned HTTP 503:

```json
{"code":"LIVE_SOURCE_UNAVAILABLE","new_fallback_case_allowed":true,"source_kind":"supplier","stage":"discovery"}
```

The safe application records show failures for `retrieve_supplier`,
`retrieve_sources`, and `retrieve_quality`, all with `WorkIQSourceError` at the
sanitized adapter boundary. These records do not retain raw exception details,
tool responses, source bodies, credentials, or discarded discovery locations.

For the supplier path, the stage is set after OBO and before MCP initialization,
`ask`, candidate parsing and binding checks. Therefore it does **not** prove that
Work IQ searched successfully and found no message. The available evidence cannot
distinguish MCP/ask failure, no usable returned locator, unsupported locator shape,
or a rejected identity/scope binding. The Quality path's internal stage is not
exposed by this attempt's public error.

No accepted live analysis, two-source evidence pair, displayed citations, Foundry
invocation, Decision, execution or outcomes are claimed. No retry, direct Graph
fallback, source edit, diagnostic endpoint, permission or billing change was made.
The application remains in live mode and fails closed.

## Next gate

The approved single attempt is spent. Further live diagnosis needs a separately
approved bounded run that distinguishes the existing discovery substeps with
allowlisted statuses/counts only, without recording message bodies, tokens or raw
tool responses. Do not replace discovery with configured IDs or weaken evidence
validation to obtain a successful-looking result.
