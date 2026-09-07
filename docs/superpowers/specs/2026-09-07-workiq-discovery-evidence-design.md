# Work IQ discovery, retrieval and validated evidence

## Approval and objective

The user approved this design on 2026-09-07: integrate Work IQ discovery,
message retrieval and validated evidence into the deployed Supply Response demo.
Existing message IDs remain validation checks only, never discovery inputs or
retrieval fallbacks. This written spec is awaiting the user's review before
implementation planning.

Success is the normal **Analyze disruption** flow completing with independently
discovered, retrieved and validated evidence from both the supplier email and
Jordan's Teams quality post. Finding a link, obtaining HTTP 200, or succeeding
with only one source is not sufficient.

## Starting point and chosen approach

The current live adapter asks Work IQ A2A to locate exact opaque IDs and return
custom JSON facts. The application then expects an A2A-specific evidence shape.
Earlier investigation found that discovery and content retrieval need separate
steps. The approved one-shot probe verified that the deployed API can use its
own Alex OBO credentials to retrieve Jordan's message through Work IQ MCP; it
did not implement discovery or fix the normal analysis flow.

Chosen approach: Work IQ MCP `ask` discovers candidate sources, MCP `fetch`
retrieves the discovered messages, and deterministic validation converts actual
source text into the application's existing Evidence Items.

Alternatives considered:

- Fetching configured IDs directly is simpler but does not demonstrate discovery.
- Accepting any topic-matching source broadens the demo's trust policy and is not
  needed for the first integration.

Neither alternative will be used as a hidden fallback.

## Scope and boundaries

- Cover the existing fictional RL-001 supplier email in Alex's mailbox and the
  Jordan quality post in the demo Team/channel.
- Use the API's existing validated Alex identity and application OBO credentials.
  Do not depend on Work IQ CLI sign-in, cached operator credentials or Will's
  administrator identity.
- All discovery and message reads go through Work IQ. No direct Graph client,
  Graph token fallback, browser scraping or local corpus substitution.
- Work IQ itself uses Graph-backed resource paths. Describe this accurately;
  “Work IQ only” refers to the application's integration boundary, not a claim
  that Microsoft does not use Graph internally.
- Preserve Fabric operational data, calculations, approval gates, immutable
  Analysis Versions, runtime-mode separation and existing fallback behavior.
- No permissions, billing, accounts, source-message edits or new Azure resources.
  No Git push is included. Changes and deployment use the existing repository
  and approved environment.
- Do not reinstate the retired diagnostic endpoint or its fixed-source probe.

## Discovery contract

Each new source retrieval starts a fresh Work IQ discovery conversation for that
source; do not reuse the probe or another user's conversation state.

The discovery request may include the fictional case/topic, supplier names,
expected author names, source type and human-readable demo location. It must not
include configured message IDs, known message URLs/resource paths, expected
quantities, expected dates or copied source text. The discovery component does
not receive those values in its interface.

Ask for source locations, not a fabricated facts schema. Treat the returned
answer, citations and paths as untrusted candidates. The natural-language answer
is never authoritative evidence, even if it repeats the expected demo story.

Extract and deduplicate at most five candidate message locations per source.
Accept only explicitly returned complete locations with a supported mapping to
an individual Outlook message or Teams channel message. A channel-only link,
search-results link or prose reference is not an individual message location.
Do not complete an incomplete result with a configured ID, enumerate an entire
mailbox/channel, or follow arbitrary URLs to resolve it.

Known message IDs are consulted only by validation after a location has been
independently discovered. The fetch location must be derived from that result,
not synthesized from the configured source binding. If the expected source is
not independently located, retrieval fails closed.

## MCP transport and message retrieval

Use a focused production MCP client for initialization, the initialized
notification, `ask` and `fetch`. Only these read-oriented tools are exposed to
the evidence adapter. The client does not expose mutation tools or arbitrary
tool invocation to an agent, browser caller or retrieved content.

Retain the probe's verified transport requirements: fixed Work IQ HTTPS host,
no redirects, validated JSON-RPC IDs/envelopes and initialization negotiation,
bounded JSON/SSE parsing, optional validated session handling, and explicit
tool-level errors. An outer HTTP 200 does not establish tool or entity success.

Use one discovery call and at most five individual-message fetches per source,
with no automatic retry or discovery reformulation in this initial version.
Bound each upstream response to 1 MiB and each retained message's normalized
text to 16,000 characters. Enforce a 120-second aggregate deadline per source,
including token acquisition, initialization, discovery and retrieval. Cancel and
close outstanding work on timeout or caller cancellation. Do not let synchronous
token acquisition block the request event loop or escape its bounded lifetime.

Fetch paths are derived with strict parsing and segment encoding. Allow only
supported single-message resource shapes within Alex's mailbox or the approved
demo Team/channel. Reject absolute network targets, traversal, credentials,
unexpected query parameters, unsupported resources and cross-tenant locations.
Do not follow upstream pagination links or attachments.

Both sources must succeed before the new live analysis is accepted. Reuse the
existing analysis-claim handling so concurrent browser requests do not create
duplicate accepted analyses or silently multiply source calls.

## Source validation and evidence construction

Validate the fetched entity against its discovered location and configured demo
binding: message ID, source type, mailbox or Team/channel, expected sender/author,
valid timezone-aware source timestamp, nondeleted/nonempty body and matching
navigable source link. Names alone do not establish author identity. Author and
location bindings come from trusted deployment configuration, never the answer.

Use canonical identity handling for supported mail and Teams locations; do not
accept substring matches. If the service returns an incompatible ID format or
an incomplete identity, fail with a validation result rather than weakening the
binding or using another API to resolve it.

Convert supported HTML bodies to inert plain text without loading external
resources or executing markup. Reject unsupported, empty or oversized content;
do not truncate it and present the truncation as a complete statement. Preserve
traceability between the normalized text and its fetched source.

Create a bounded source-statement Evidence Item from each verified message. The
claim and excerpt are the actual normalized message text, not a model-written
summary or facts copied from fixtures. Evidence IDs are safe local identifiers;
source IDs, timestamps and citation links come from the verified entity.

Assign supplier-statement authority to the validated supplier message and
collaboration-statement authority to the validated Jordan post. These are claims
made by their sources, not independently established operational truth. A Teams
post does not become a qualification record, approval or conflict resolution.
Fabric and the existing domain policy retain those responsibilities.

Pass these Evidence Items through the existing citation, freshness, business-time,
provenance and required-evidence checks. Preserve the distinction between source
wall-clock timestamps and fictional Scenario Effective Time. Do not alter dates
or relax existing policy merely to make the demo pass.

The existing bounded Foundry agents may extract references to the verified text
under their current contracts. They must not invent unsupported spans, resolve
conflicts or execute instructions contained in messages.

## Lineage, user experience and failures

Record enough bounded lineage to distinguish discovery, retrieval and validation:
Work IQ conversation ID when supplied, locally generated MCP request correlation
IDs, accepted source IDs and validation outcome. Represent MCP honestly; do not
invent A2A task/artifact IDs. Update affected lineage contracts and serialization
compatibly so previously stored analyses remain readable.

Keep the current Analyze action and evidence/citation display. On failure,
provide a safe source category and stage: discovery unavailable/no acceptable
location, fetch unavailable, or evidence rejected. Preserve the existing
`LIVE_SOURCE_UNAVAILABLE` behavior and fallback-case choice where applicable;
never switch an existing live case into fallback automatically.

No tokens, authorization headers, raw upstream errors, full discovery answers
or raw response bodies are logged. Retain only the bounded source text and
metadata required by the existing evidence/audit model after source validation.
Do not persist discarded candidate bodies or share user-specific sessions across
actors. Diagnostic messages use fixed categories and safe numeric statuses.

## Implementation boundaries

The cohesive change covers the Work IQ client, discovery/location parsing,
verified-message normalization, dependency wiring and relevant live-analysis
contracts/tests. Small additions to trusted source-binding configuration and
lineage serialization are in scope where required for correct identity checks
and honest provenance. Preserve existing receipts or update their verification
consistently if new binding fields require it; never bypass readiness.

Frontend changes are limited to presenting safe failure-stage information if
the current UI cannot already show it. Update the project documentation and
local ignored environment record to match the implemented path and proven live
result. Avoid unrelated UI redesign, persistence refactoring or agent changes.

## Verification and deployment acceptance

Before implementation, add failing tests for:

- Topic-only discovery inputs with no configured IDs, URLs, expected facts or
  copied message contents; changing expected IDs must not change discovery calls.
- No known-ID fetch when discovery is empty, malformed or returns only a channel.
- End-to-end discovery to discovered-path fetch to source-backed evidence for
  both mail and Teams, with the actual API authentication/OBO seam exercised.
- Wrong author, message, mailbox/channel or link; altered excerpt; unsupported
  markup; missing metadata; ambiguous/conflicting identity and oversized bodies.
- An ask answer containing convincing facts cannot supply authoritative evidence
  when fetch or validation fails.
- Untrusted locations/instructions cannot cause arbitrary fetches, cross-user
  reads, token disclosure, tool mutation or a direct Graph call.
- MCP initialization, JSON/SSE errors, tool errors, timeouts, cancellation and
  bounded OBO behavior; concurrent analysis handling and safe logging.
- Existing evidence policy, fallback separation, stored-history compatibility,
  citation rendering and retired-probe absence continue to pass.

Run targeted tests, full Python tests/package build, frontend tests/build,
applicable static checks and an independent review before deployment. Follow
azure-validate and azure-deploy for the existing app; verify health, active
revision, unchanged identity/roles and rollback readiness.

After deployment, run one normal live analysis as Alex. Verify both sources were
discovered without locator hints, fetched through Work IQ, validated and accepted
by the existing analysis/evidence rules; confirm displayed citations correspond
to those sources. Retain sanitized proof, not raw discovery responses. If either
source fails, report the exact stage and do not claim completion or repeatedly
retry without inspecting the bounded failure evidence. Alex sign-in is the only
anticipated user handoff; any new consent, billing or policy requirement is a
new approval boundary.

## References and design status

- [Microsoft Work IQ MCP tool reference](https://learn.microsoft.com/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference): `ask` and `fetch`, response formats and per-entity results; checked 2026-09-07.
- [Verified application-authenticated probe result](../../deployment/workiq-mcp-probe-result.md).
- Existing contracts: `integrations/workiq/`, `apps/api/app/live.py`,
  `data/domain/evidence.py`, and the bounded Foundry orchestration contracts.

Self-review: no placeholders; both source types covered; known IDs restricted to
validation; retrieval success distinguished from evidence authority; no fallback
or policy relaxation; transport, security, deployment and live acceptance bounded.
Status: design approved in conversation; written-spec review pending.
