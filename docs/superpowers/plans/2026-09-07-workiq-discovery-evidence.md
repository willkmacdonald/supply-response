# Work IQ Discovery and Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete normal Alex analysis using independently discovered and fetched Work IQ mail/Teams evidence.

**Architecture:** An isolated MCP session and bounded asynchronous OBO boundary serve a discovery/evidence adapter. Discovery has no known locators in its interface. The live application consumes verified source statements and honestly labeled MCP lineage through its existing analysis gates.

**Tech Stack:** Python/FastAPI/MSAL/httpx, existing Pydantic/domain models, React, pytest/Vitest, existing Azure Container App deployment scripts.

## Global Constraints

- Approved spec: `docs/superpowers/specs/2026-09-07-workiq-discovery-evidence-design.md` (read fully).
- Existing message IDs remain validation checks only, never discovery inputs or retrieval fallbacks.
- All discovery and message reads go through Work IQ. No direct Graph client, Graph token fallback, browser scraping or local corpus substitution.
- Use the API's existing validated Alex identity and application OBO credentials.
- Use one discovery call and at most five individual-message fetches per source, with no automatic retry or discovery reformulation in this initial version.
- Bound each upstream response to 1 MiB and each retained message's normalized text to 16,000 characters. Enforce a 120-second aggregate deadline per source, including token acquisition, initialization, discovery and retrieval.
- No permissions, billing, accounts, source-message edits or new Azure resources. No Git push is included.
- Do not reinstate the retired diagnostic endpoint or its fixed-source probe.
- Preserve Fabric operational data, calculations, approval gates, immutable Analysis Versions, runtime-mode separation and existing fallback behavior.
- Controller owns all cloud execution; implementers/reviewers use offline fixtures only and never invoke live Work IQ.
- Work in the existing user-approved main checkout. Preserve unrelated changes. Use apply_patch, TDD and local commits.

## File map and execution order

1. `integrations/workiq/mcp.py`: reusable narrow MCP session/client. `integrations/workiq/async_obo.py` and `integrations/workiq/obo_http.py`: bounded per-call OBO production resources. `obo.py`: backwards-compatible injection seam only if necessary. No runtime switch yet.
2. `integrations/workiq/discovery.py`: topic inputs and response candidates. `locations.py`: strict source-location parsing. `message_evidence.py`: actual entity validation/normalization. `mcp_evidence.py`: orchestration. `models.py`: MCP provenance extension preserving A2A callers.
3. Live settings/dependency wiring, trusted binding environment plumbing, lineage contracts and safe failure UI/API propagation. Documentation/tests updated with the runtime switch.
4. Controller performs final suite, independent review, approved environment validation/deployment, then one Alex live analysis.

### Task 1: Isolated MCP and bounded asynchronous OBO

**Files:** Create `integrations/workiq/mcp.py`, `integrations/workiq/async_obo.py`, `integrations/workiq/obo_http.py`, `tests/integration/test_workiq_mcp_transport.py`, `tests/integration/test_workiq_async_obo.py`. Modify `integrations/workiq/obo.py` only for a backwards-compatible optional HTTP injection seam; broaden `errors.py` protocol wording beyond A2A.

**Interfaces:**

```python
# mcp.py; public methods expose only the two allowed tools.
class WorkIQMcpClient:
    def __init__(self, *, http: httpx.AsyncClient): ...
    def session(self, *, access_token: str): ...  # async context manager

class WorkIQMcpSession:
    async def ask(self, question: str) -> dict[str, Any]: ...
    async def fetch(self, entity_url: str) -> dict[str, Any]: ...
    @property
    def request_ids(self) -> tuple[str, ...]: ...

# async_obo.py; each exchange owns its MSAL client/cache and bounded HTTP adapter.
class AsyncWorkIQOboExchange:
    def __init__(self, *, client_id: str, client_secret: str,
                 tenant_id: str, auth_service: AuthService): ...
    async def exchange(self, actor: AuthenticatedActor) -> WorkIQAccessToken: ...
```

The session context initializes protocol `2025-03-26`, validates server version/capabilities/serverInfo, sends the initialized notification and holds optional validated session/protocol headers only for its lifetime. Use JSON-RPC IDs for correlation. Parse tool structuredContent or JSON text wrappers into dictionaries. `ask` returns a validated `response` string and `conversationId` string; `fetch` returns the documented one-element `results` list containing entity `data` and numeric `statusCode`. Reject tool `isError`, JSON-RPC errors, mismatched IDs and unsuccessful entity status. A client can share an httpx connection pool but not session state or actor tokens.

- [ ] Write failing transport tests with MockTransport covering successful initialize/notification/ask/fetch plus outer200/tool-error, mismatched IDs, optional session headers, valid multiline SSE, 3xx rejection, malformed/oversized/deep JSON, cancellation and two concurrent token-separated sessions. Example essential assertion:

```python
async with client.session(access_token="fixture-token") as session:
    answer = await session.ask("Find the fictional supplier disruption email")
    assert answer["conversationId"] == "fixture-conversation"
    assert answer["response"] == "fixture source location"
assert [request.method for request in requests] == ["POST", "POST", "POST"]
assert all(request.url.host == "workiq.svc.cloud.microsoft" for request in requests)
```

- [ ] Run `.venv/bin/pytest -q tests/integration/test_workiq_mcp_transport.py` and record expected missing-feature failures.
- [ ] Implement fixed `https://workiq.svc.cloud.microsoft/mcp`, no redirects/retries, exact HTTP200 RPC success/202 empty notification semantics, 1 MiB streaming response bound, depth20 parsing, bounded headers and no raw exception/body logging. Session methods generate exact tool arguments: `{"question": question}` and `{"entityUrls": [entity_url]}`; never arbitrary tool names. Apply instrumentation suppression to token-bearing outbound operations.
- [ ] Write failing actual AuthService/signed-JWT OBO tests: valid Alex succeeds through the real builder/MSAL HTTP seam using fake Entra HTTP; wrong actor/roles/audience/scopes cannot acquire a token; malformed/oversized/token-response errors do not leak; event loop remains responsive; cancellation leaves no unbounded worker or retained cache.
- [ ] Implement the async exchange around the existing `WorkIQOboExchange` actor validation. Bound aggregate OBO HTTP to 12 seconds and responses to 1 MiB. Use a per-exchange lazy MSAL client with a bounded safe HTTP adapter. Sanitize token endpoint results before MSAL sees them to prevent raw non-JSON logging; allow only required OAuth fields and existing safe error codes. Ensure deadline/cancellation cleanup joins bounded work and closes all clients/cache references. Historical `5fe3591` probe transport is a reference, not a diagnostic module to restore.
- [ ] Run both new test files plus existing `tests/integration/test_workiq_obo_diagnostics.py`, auth/Work IQ contract tests, scoped Ruff/Pyright; full pytest once before commit. Commit and write RED/GREEN evidence to the report file. Task is complete only after independent task review.

### Task 2: Locator-independent discovery and verified message evidence

**Files:** Create `integrations/workiq/discovery.py`, `integrations/workiq/locations.py`, `integrations/workiq/message_evidence.py`, `integrations/workiq/mcp_evidence.py`; extend `integrations/workiq/models.py`; tests `tests/integration/test_workiq_discovery.py`, `test_workiq_message_evidence.py`, `test_workiq_mcp_evidence.py`.

**Interfaces:** Consume Task1 client/session and async OBO `exchange(actor)`; introduce the following immutable typed inputs:

```python
@dataclass(frozen=True, slots=True)
class DiscoveryTopic:
    source_kind: Literal["supplier", "quality"]
    case_reference: str = "RL-001"
# question_for(topic) is the only discovery prompt builder; no binding argument.

@dataclass(frozen=True, slots=True)
class SourceBinding:
    tenant_id: str
    alex_object_id: str
    supplier_sender: str
    quality_author_object_id: str
    team_id: str
    channel_id: str
    supplier_source_id: str
    quality_source_id: str

class WorkIQMcpEvidencePort:
    def __init__(self, *, client: WorkIQMcpClient,
                 obo: AsyncWorkIQOboExchange, binding: SourceBinding): ...
    async def retrieve_supplier_signal(self, *, actor, source_id, case_id,
                                       analysis_id, retrieved_at) -> WorkIQRetrieval: ...
    async def retrieve_quality_context(self, *, actor, source_id, case_id,
                                       analysis_id, retrieved_at) -> WorkIQRetrieval: ...
```

Keep both public retrieval signatures compatible with `apps/api/app/live.py`. The `source_id` argument must equal the configured validation binding but never reaches the prompt or supplies a fetch path. `WorkIQRetrievalLineage` adds backwards-compatible `protocol` (default `a2a`) and `request_ids` fields; MCP uses real conversation IDs, empty A2A task/artifact values and `protocol="mcp"`.

- [ ] Write RED discovery tests. `question_for(DiscoveryTopic("supplier"))` asks for the RL-001 fictional Alpha supplier email in the user's mailbox; quality asks for Jordan's Beta qualification post in Supply Response Demo/General. No IDs, URLs, expected quantities/dates or pasted body. Changing SourceBinding IDs produces identical ask requests. Parse at most5 deduplicated complete candidate message locations from returned response JSON or explicit links; reject prose/channel-only/search/unsupported links. Ask answers never directly produce EvidenceItems.
- [ ] Implement strict individual-message location types and parser. Supported Teams canonical deep links resolve complete team/channel/message identifiers; supported Outlook item URLs or explicitly returned mailbox message resource paths resolve individual messages. Paths are derived from discovery with segment encoding; reject external hosts, traversal/encoded traversal, duplicate/conflicting query identities, arbitrary queries, unsupported ports/userinfo and incomplete paths. Bind mailbox to `/me` or the exact Alex object ID; bind Teams to exact configured team/channel. Do not use configured message IDs to complete locators. No listing/attachments/pagination/Graph calls.
- [ ] Write RED entity tests using fictional bodies that differ from known fixture answers. Validate ID, sender/author, location, body, timestamp, navigable source link and discovery-to-fetch identity. For mail, validate sender and mailbox; for Teams, author object ID and channelIdentity. Reject deleted messages, empty or unsupported bodies and over16000-character normalized text. Convert HTML with a safe standard-library parser without loading/executing resources. Test scripts/styles, encoded characters and text traceability.
- [ ] Construct exactly source-backed claims, not extracted model facts:

```python
assert evidence.claim == normalized_fetched_body
assert evidence.excerpt == normalized_fetched_body
assert evidence.source_id == fetched_message_id
assert evidence.authority_scope == (expected_scope,)
assert evidence.source_system is EvidenceSourceSystem.WORK_IQ
assert evidence.runtime_mode is RuntimeMode.LIVE
```

Use safe locally generated evidence IDs and the fetched source timestamp/link. Retain normal evidence-policy checks downstream. Supplier scope is SUPPLIER_STATEMENT; quality scope is COLLABORATION_STATEMENT, never qualification/approval authority. Preserve existing demo synthetic/provenance convention rather than changing fixture metadata.
- [ ] Implement port orchestration under `asyncio.timeout(120)`: exchange actor token; open isolated MCP session; call ask once; validate locations independently of known IDs; use expected IDs only to validate discovered candidates; fetch at most5; accept only exactly matching validated source. Fail closed if absent/invalid/ambiguous. No retries. Carry actual conversation and request IDs into MCP lineage. Close token/session references after the call.
- [ ] Add safe typed source/stage failure (`discovery`, `fetch`, `validation`, `authentication`, `timeout`) without raw payloads. Test missing discovery causes zero fetch calls, wrong configured IDs cannot alter ask/fetch locators, failed fetch cannot promote ask prose, cross-user inputs rejected, deadlines/cancellation and exact source excerpts.
- [ ] Run new tests plus transport/async OBO and existing Work IQ trust-boundary suites; full pytest before commit; scoped Ruff/Pyright. Commit, report RED/GREEN evidence, then independent task review.

### Task 3: Connect the live demo and preserve provenance

**Files:** Modify `apps/api/app/settings.py`, `dependencies.py`, `live.py`; lineage contracts `data/domain/analysis.py`, `agents/orchestrator/contracts.py`; related serializers only if necessary. Bindings in `infra/main.bicep`, relevant modules/parameters and deployment/preflight scripts. Tests in existing live-dependency/live-analysis suites plus `tests/integration/test_workiq_mcp_live_wiring.py`. Relevant README/roadmap/deployment docs. Frontend api/error display only if needed for safe stage information.

**Interfaces:** Wire Task2 `WorkIQMcpEvidencePort` with Task1 `WorkIQMcpClient` and `AsyncWorkIQOboExchange` and trusted `SourceBinding`. Existing settings for IDs, tenant/Alex remain. Add nonsecret required live settings `workiq_supplier_sender`, `workiq_quality_author_object_id`, `workiq_team_id`, `workiq_channel_id`. Thread these through existing env/Bicep/preflight validation. No embedded tenant-specific IDs in production code.

- [ ] Write RED dependency tests proving live mode selects the MCP evidence port and existing fallback mode is unchanged. Missing/inconsistent new binding values fail readiness before source access. Test existing binding receipts remain validated and any changed receipt schema is consistently versioned across producer/checker; do not bypass receipt verification.
- [ ] Wire new port and bounded async OBO without changing actor authentication or acquiring additional scopes. Reuse the application's connection lifecycle with isolated MCP sessions. Update deployment env plumbing and local deployment documentation to list all required bindings; controller supplies verified existing values at deployment.
- [ ] Write RED compatibility tests for old stored A2A lineage and new MCP lineage. Add protocol/request_ids defaults to AnalysisRetrievalLineage and orchestration RetrievalLineage; pass them explicitly from the adapter. Do not fabricate A2A task/artifact IDs. Preserve serialization and old snapshots without schema migration where current JSON storage supports it.
- [ ] Write a normal live-analysis integration test using real signed Alex auth, mocked Entra/MCP HTTP and existing operational fixtures: discovery→fetch both sources, actual body EvidenceItems, analysis accepted, correct citations/classification/lineage. Verify no known-ID discovery prompts, no direct Graph network requests, existing claims/concurrency and failure release. Test source-stage failure survives the existing generic503 wrapper as fixed safe fields, with no raw body/error/token output.
- [ ] Preserve normal freshness/business-time/authority checks; do not alter or backdate source timestamps. Existing Foundry extraction receives bounded verified text under its unchanged contracts. Run existing policy and orchestration tests and safe model-boundary checks.
- [ ] Update safe UI failure copy if required to identify supplier vs quality and discovery vs fetch vs validation. Successful existing evidence/citation presentation should work without redesign. Tests pin fallback-case behavior and prohibit automatic runtime-mode switching.
- [ ] Update existing README/roadmap/docs: Work IQ ask discovers, fetch retrieves, validated text supplies source statements; Graph is only internal to Work IQ; known IDs are validation bindings. Distinguish local verified code from unproven live success until controller observation.
- [ ] Run full pytest, uv build, frontend tests/build, scoped Ruff/Pyright, diff checks; commit and independent task review. Then whole-change review against baseline91c1681. Fix any Critical/Important findings with tests before cloud changes.

### Task 4: Controller validation, deployment and one live analysis

**Files:** `.azure/deployment-plan.md`, ignored local environment record, sanitized deployment outcome document and progress ledger. No new public diagnostic route.

- [ ] Verify trusted source bindings from existing local deployment record and narrowly scoped read-only metadata where needed; no new message reads before approved normal analysis. Populate four nonsecret binding values through existing environment configuration; do not display credentials.
- [ ] Follow azure-validate: preflight, current identity/subscription/region, preview, builds/package, exact static/live roles and validation proof. No new resources or roles. Confirm approved main clean/committed and record baseline active revision for rollback.
- [ ] Follow azure-deploy and existing `scripts/deploy_personal_tenant.sh --apply`, then approved `--smoke`; verify active revision/image/health, unchanged roles, and retired-probe route absent. No Git push.
- [ ] Use actual Alex browser session in the demo, creating a single showcase Case only if needed, then invoke normal Analyze once. Observe discovery/fetch/validation safe stages, both evidence citations and completed analysis. Never approve a Decision or run execution actions in this task.
- [ ] If unsuccessful, inspect safe categorized diagnostics once and report exact stage; do not claim success, retry repeatedly, substitute Graph or broaden permissions/billing. Fix verified in-scope code defects through tests/review/deploy before a separately explained next live attempt. If sign-in or new authority is required, ask the user precisely.
- [ ] Save sanitized final proof, update documentation status and ledger, commit locally; report result, limitations and demo link.

## Self-review and progress

Spec sections map to transport/OBO(Task1), discovery/source trust(Task2), app/persistence/UI compatibility(Task3) and live acceptance(Task4). Public interfaces are explicit; both source types and failure boundaries are covered. No implementation task receives real tenant credentials. Topic-only discovery is independent from validation IDs by construction and tested by perturbing bindings.

- [ ] Task1 reviewed complete.
- [ ] Task2 reviewed complete.
- [ ] Task3 and whole-change review complete.
- [ ] Task4 live acceptance complete, or precise blocker recorded.
