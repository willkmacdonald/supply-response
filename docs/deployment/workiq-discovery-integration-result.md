# Work IQ discovery/evidence integration — deployment and acceptance result

Updated 2026-09-08 UTC. This records deployment separately from live acceptance.

## Current result — both Work IQ sources validated live; Teams citation UI blocked

Release `5fea43f`, ACR build `ch18`, activated revision `ca-sr-demo--0000018`
with immutable digest `f05099e8170e50bca8e1774c45be91b58752ea8d0bac9605a1f82c33ac1ad760`.
The sole active/latest-ready revision is Healthy/Running; identity, exact three
scoped Azure roles and scale0–2 are unchanged. Post-deploy Fabric/Foundry readiness
passed. The supplier binding and receipt match the verified local configuration.
`azd show` confirms the same environment; Container App ingress confirms the
[existing HTTPS demo](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/).

At approximately06:11 UTC, one normal Analyze in Alex's existing Case completed
through the deployed application MCP/OBO path. The UI displayed five evidence
items: three Fabric items plus the full approved supplier and Jordan statements,
both marked `work_iq healthy`. It displayed the combined response recommendation,
2,300 uncovered units and $24,750 response cost; Supplier Beta remained blocked
for pending qualification. This establishes application discovery, individual
reads and accepted source evidence, not merely standalone CLI success.

Remaining issue: the UI reports `Required live citation missing`. Supplier mail
has an Open citation link; the Jordan Teams evidence has no link. Approve and
Reject remain disabled. The selected-source backend validator required a valid
matching citation, but the exact loss/rejection point in presentation is not yet
established. Local inspection confirms citation classification/navigation fields
are assigned in the live service and checked again by the frontend. Do not claim
the full live journey is complete, bypass this gate, or regenerate analysis to
hide the issue. No Decision, execution, source edit, second Analyze or Git push
occurred. A subsequent read-only browser diagnostic stalled and returned no
captured API responses; it did not establish the citation's failure cause.

Independent review corrected malformed/duplicate collection handling and restored
safety coverage. Final full Python regression, Python package, scoped Ruff/Pyright
including tests, frontend51 tests/build and focused regressions passed. Review
approved with no remaining findings; expected14 live-test skips remain.

## Implementation and binding reconciliation

The approved implementation replaces answer-link extraction in the live MCP path
with bounded Work IQ entity queries: supplier-topic mail search, and named team /
channel resolution followed by a bounded post collection. It then fetches each
independently discovered message individually and applies the existing evidence
checks. This is structured Work IQ querying, not semantic `ask` discovery or a
direct Graph client. Structured retrieval records MCP request IDs without
inventing a Copilot conversation ID.

The supplier binding was reconciled locally after a fresh explicit Alex identity
check, unique sender/topic discovery, exact approved corpus comparison and the
existing evidence validator. Only the supplier source ID and derived receipt
changed in the ignored environment; rollback values remain in ignored notes.
The verified binding was subsequently deployed with revision18. The live source
acceptance result and separate UI citation blocker are recorded above.

## Previous investigation — content readable; supplier binding mismatch isolated

A bounded Alex Work IQ CLI investigation found that supplier `ask` citations and
a structured mail search converge on the same email after Outlook ID conversion.
Its individually fetched body exactly matches the approved 249-character corpus,
but its ID differs from the configured supplier source ID. No binding was changed.
Structured Team/channel discovery independently located Jordan's expected post;
its individual read passed the existing evidence validator. Natural-language
Teams discovery still returned different chat-context identities.

These are operator diagnostic results, not deployed MCP/OBO acceptance or a
successful analysis. The website is unchanged. See the
[live investigation record](../research/2026-09-08-workiq-discovery-live-result.md)
and [Microsoft contract research](../research/2026-09-08-workiq-discovery-contract.md)
for the exact checks and the design decision needed before integration.

## Current local correction — Outlook links parse; evidence gate still blocked

The user approved the targeted format correction and retrieval/evidence checks
before another deployment. No new revision was deployed; revision17 below remains
the deployed baseline.

Bounded Work IQ CLI inspection explicitly used `agent@willmacdonald.com` and kept
answers in process memory. Outlook citations contained an EWS-format ItemID with
`/` and UUID-valued `EntityRepresentationId` metadata. The local parser now allows
that metadata and applies Microsoft's Outlook `convertToRestId` mapping (`/` to
`-`, `+` to `_`) only at the OWA ItemID boundary. An unfragmented live citation
retained in memory changed from rejected to one deduplicated location. REST paths,
query allowlists, duplicate-key checks and fragment rejection remain unchanged.

The Teams results were `contextType=chat` links, not complete channel-message
locations. They remain rejected; no configured team ID is inserted. The Quality
question now explicitly requests a complete channel location and excludes chat
and search links, without giving it source IDs or expected facts.

A subsequent bounded CLI check used the current questions, parser, trusted source
bindings, and existing evidence validator. Safe outcomes:

```text
supplier: parsed=1 scoped=1 matched=0; no fetch
quality: parsed=0 scoped=0 matched=0; no fetch
```

All six local source/author/location binding values were independently compared
with the deployed Container App and matched. The supplier mismatch is not yet
diagnosed as a different message versus an additional ID-format issue. The
Quality answer supplied no complete supported channel location. Neither source
reached live entity validation, and no validated evidence pair is claimed.

Four parser/prompt regressions failed before implementation and passed afterward.
The targeted parser/evidence/live-wiring suites passed 124 tests; an independent
reviewer found no actionable issues and separately passed 84 tests. Scoped
Ruff/Pyright and the Python package build passed. Full Python regression passed
1,055 tests with 14 expected skips and the existing Starlette/httpx deprecation
warning. The first sandboxed run had four Power BI dependency-restore failures;
the rerun with public NuGet access passed without code changes. No raw answers,
source bodies, or credentials were persisted; temporary operator scripts were
removed after their processes exited. No commit or push in this correction turn.

This CLI check is not deployed application/OBO acceptance. Do not relax bindings,
fetch configured IDs, reinterpret chats as channel posts, or deploy another
supposed complete fix without proving both source paths.

References: [Microsoft Outlook implementation](https://appsforoffice.microsoft.com/lib/1/hosted/outlook-web-16.01.js),
[Teams chat versus channel link semantics](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/deep-link-teams).

## Deployed baseline — field handling fixed; no recognized locations, revision17

The user approved the correction, deployment and one normal Alex Analyze.
Commit `5566822` accepts either bounded `answer` or documented `response`,
normalizing to the existing internal field. Explicit invalid aliases and
conflicting values fail closed. Metadata, conversation checks, topic-only prompts,
discovered-only fetch and evidence validation remain intact.

The observed-field fixtures reproduced22 failures before the fix. Afterward,
112 focused tests, full Python regression/package,51 frontend tests/build and
scoped Ruff/Pyright passed. Independent review found no actionable issues and
independently passed112 tests. No new resources or permissions in preview.
Successful ACR build `ch17` deployed revision `ca-sr-demo--0000017`, digest
`f9bb03126cb284537dee9353b0c9d699938df0315d57572df8869d8ffe2d0d0a`.
It is sole active/latest-ready, Healthy/Running with100% traffic; exact identity,
three Azure roles and scale0–2 are unchanged. Post-deploy readiness passed.

At approximately02:54 UTC on September8, one normal Alex Analyze used the same
existing Case without refresh. The UI still reports supplier/discovery503.
Allowlisted diagnostics for that attempt:

```text
source=supplier stage=discovery step=parse_locations reason=no_locations http_status=0 parsed=0 scoped=-1 matched=-1
source=quality stage=discovery step=parse_locations reason=no_locations http_status=0 parsed=0 scoped=-1 matched=-1
```

The field correction is verified live: both ask results passed field validation
and reached locator parsing. Neither yielded a location recognized by our parser.
Scope/message-binding checks and fetch were not reached. This does not establish
whether Work IQ returned no links or returned an unsupported link format; the
answer text was not inspected. No message retrieval, validated evidence pair or
downstream acceptance is claimed. No second attempt, body capture or Git push.

Next boundary: distinguish absent message links from unsupported locator formats
using a separately approved bounded inspection. Do not fetch configured IDs,
relax source validation or repeatedly retry the same analysis.

## Previous diagnostic result — confirmed answer-field mismatch, revision16

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

The then-proposed gate, completed by revision17 above: approve a tested adapter correction for the confirmed answer
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
