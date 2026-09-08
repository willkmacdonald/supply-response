# Work IQ discovery/evidence integration — deployment and acceptance result

Updated 2026-09-08 UTC. This records deployment separately from live acceptance.

## Current diagnostic result — confirmed answer-field mismatch, revision16

The approved field-status-only diagnostic implementation `664b67f` is deployed
as ACR build `ch16`, revision `ca-sr-demo--0000016`, immutable digest
`042a556dcf974e5fb8d045709d068ea92556c4c8263b0eba7fd03069652aa2a9`.
Revision16 is sole active/latest-ready, Healthy/Running with100% traffic.
Post-deploy readiness, endpoint/environment and exact three-role checks passed;
identity and scale0–2 are unchanged. Full Python regression/package,95 focused
tests,51 web tests/build, scoped static checks and independent review passed.

One normal Alex Analyze used the existing Case, without refreshing or creating
another Case. The result was confirmed at approximately02:33 UTC on September8:
the same supplier/discovery503. Both supplier and Quality logged:

```text
workiq_ask_shape response=missing conversation_id=valid answer=valid error=missing
```

Both corresponding source records retain step=ask, reason=discovery_shape,
http_status=0 and parsed/scoped/matched=-1. Here valid means a nonempty string
within the configured bound, not validated evidence or useful answer content.

This confirms the immediate adapter defect: the decoded Work IQ result uses
`answer`, whereas our adapter requires `response`. Its rejection prevents locator
parsing and message retrieval. Microsoft's [tool reference](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference)
describes `response`/`conversationId`, but its [iq-series lab](https://github.com/microsoft/iq-series/blob/main/Work-IQ/3-Work-IQ-Tooling-with-MCP-and-Copilot-CLI/cookbook/work-iq-lab03.md)
describes structured content with `answer`/`conversationId`, consistent with the
observed field states. No raw values, arbitrary keys, identifiers, credentials or
message bodies were logged. This does not prove the answers contain usable
locations or that the requested messages were found. No evidence or downstream
live acceptance is claimed.

Next proposed gate: approve a tested adapter correction for the confirmed answer
field, preserving strict bounds, source validation and discovered-only fetch;
then deploy and perform one normal Alex Analyze. No parser fix, second Analyze,
new permissions, billing, source edits, Graph fallback or Git push occurred in
this diagnostic follow-up.

## Previous diagnostic follow-up — revision15

The user separately approved failure-only substep diagnostics and one further
normal Alex Analyze, without raw-response capture or permission changes.
Implementation `0d5cb0a` and validation/test-isolation commit `e145843` were
deployed as ACR build `ch15` and revision `ca-sr-demo--0000015`. Immutable digest:
`d9341d15de084ff516d7d125218bf821965cd3e095adb519a98e760eac921c9a`.
Revision15 is sole active/latest-ready, Healthy/Running, 100% traffic; scale0–2,
identity and the exact three Azure roles are unchanged. Live readiness passed.
Full Python regression exited0; 51 web tests/build, scoped static checks, package
and independent reviews passed. No Git push.

At approximately 02:14 UTC on September8, the existing Alex-authenticated Case
was analyzed once, without refreshing the browser or creating another Case.
The same public supplier/discovery 503 was returned. New safe diagnostics:

```text
source=supplier stage=discovery step=ask reason=discovery_shape http_status=0 parsed=-1 scoped=-1 matched=-1
source=quality stage=discovery step=ask reason=discovery_shape http_status=0 parsed=-1 scoped=-1 matched=-1
```

Both paths completed OBO and MCP initialization and reached the `ask` answer
validation in `WorkIQMcpSession.ask`. The decoded tool result did not satisfy
the adapter's expected nonempty string `response` (maximum1MiB) and nonempty
string `conversationId` (maximum256characters) contract. These statuses do not
identify which field, type or bound failed. `http_status=0` means no HTTP-error
status was recorded, not an HTTP response status. Counts of-1 mean the locator
parsing/binding stages were never reached.

This is not proof that discovery returned no messages or that message contents
are inaccessible. No locator was parsed or fetched in this attempt; validated
evidence and downstream live acceptance remain unverified. No raw responses,
message bodies, tokens or new source identifiers were captured. No retry,
direct Graph fallback, permissions, billing, source edits or policy changes.

The then-proposed gate, completed by revision16 above: inspect only allowlisted answer-field presence/type/bounds
or a verified upstream contract to determine why the shape check rejects it;
then fix and test the adapter contract. Any additional live diagnostic invocation
needs approval. Do not weaken evidence validation or hard-code discovery IDs.

## Previous integration deployment — revision14

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

## Previous next gate (completed by the diagnostic follow-up above)

The approved single attempt is spent. Further live diagnosis needs a separately
approved bounded run that distinguishes the existing discovery substeps with
allowlisted statuses/counts only, without recording message bodies, tokens or raw
tool responses. Do not replace discovery with configured IDs or weaken evidence
validation to obtain a successful-looking result.
