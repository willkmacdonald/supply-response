# Supply Response Roadmap

**Last updated:** 2026-09-04
**Source of truth:** [Frozen demo contract](superpowers/specs/2026-08-30-supply-response-demo-contract-design.md) and [implementation plan](superpowers/plans/2026-08-30-supply-response-demo-implementation.md)

This roadmap reports the durable, reviewed repository baseline. Uncommitted or actively developed work is not counted as complete.

## Status summary

| Area | Status | Current boundary |
|---|---|---|
| Contract, domain model, and ADRs | Complete | Frozen contract, glossary, and four ADRs are committed |
| Deterministic decision quality | Complete | Canonical RL-001 and all ten focused evaluation cases are integrated |
| Durable closed-loop backend | Complete | SQLite persistence, immutable Decisions, outbox, five actions, attempts, playback, and observations are covered |
| Web decision console | Complete in fallback mode | Progressive workspace and browser journey pass locally |
| Fabric SQL | Live setup validated; managed-identity grant pending | Dedicated `Supply Response Demo` workspace and `SupplyResponseDemo` SQL Database exist; schema version 12 is live, both scripts were applied twice, and the approval-gated live SQL integration test and health check passed; the future Container App managed-identity grant remains |
| Power BI | Published; empty-state live render validated | The semantic model and two-page report are published, OAuth2-bound to Fabric SQL, DAX-queryable, and visually clean with an empty database; populated Decision-ID parity remains a post-application-deployment gate |
| Entra ID and persona authorization | Implemented and tenant-configured; live gate pending | API/SPA registrations, exact delegated consent, persona bindings, and role assignments are verified in `willmacdonald.com`; deployed authenticated flows have not run |
| Work IQ | Demo Corpus configured; live retrieval pending | Tenant enablement, exact delegated consent, supplier email and Jordan-authored Quality sources, deployment bindings, and the deterministic receipt are verified; approval-gated live cited retrieval remains |
| Foundry orchestration | Implemented and agents published; invocation pending | Signal, context, and decision agents are verified as immutable version `1` contracts on `gpt-5.6-luna`; no live invocation or evaluation has run |
| Complete live Case journey | Implemented locally; live gate pending | Fail-closed live composition, durable lineage, readiness, and browser contracts are covered; deployment-dependent bindings and a full live run remain |
| Personal-tenant deployment and hardening | Azure application deployed; post-deployment gates pending | The resource group, Container App, Application Insights, Key Vault, immutable image, secret binding, and exact Azure RBAC assignments are live; Fabric SQL identity access and live acceptance checks remain |

## Delivery sequence

### 1. Contract and portable core — complete

Tasks 0–4 established the frozen contract and reconciled the portable core with it.

- Canonical domain language and Case Instance model
- Frozen RL-001 operational facts and expected outcomes
- Evidence, approval, and analysis-version policy
- Deterministic option evaluation and thresholded lexicographic ranking
- Integrated coverage for ten focused evaluation cases

### 2. Durable closed loop — complete

Tasks 5–9 implemented the local application lifecycle.

- Explicit runtime configuration and persistence ports
- Durable, append-only, idempotent Decisions
- Transactional outbox and exactly five bounded Execution Actions
- Execution-attempt history and deterministic Simulated Execution
- Decision-linked Outcome Observations
- Closed-loop FastAPI application service

### 3. Fallback decision experience — complete

Tasks 10–11 delivered and proved the local decision experience.

- Progressive React Case workspace
- Evidence, exposure, option, recommendation, and approval views
- Immutable Decision receipt
- Action, playback, observation, and variance views
- Explicit fallback and simulation labeling
- Full Python, Vitest, production-build, and Playwright fallback gate

### 4. Fabric and Power BI — live SQL and Power BI publication validated

Tasks 12–13 implemented the live persistence and reporting artifacts. The dedicated
Fabric SQL setup and Power BI publication were completed under approval-gated live
checks.

Completed locally:

- Fabric SQL adapter using Entra tokens and explicit credential selection
- Operational schema, schema-version health checks, and retry-safe deployment path
- Decision-linked `analytics.case_command_center` and `analytics.action_outcomes` views
- Two-page Power BI Project: **Command Center** and **Actions and Outcomes**
- DirectQuery semantic model and deployment preflight
- Offline Microsoft schema validation and semantic-model parsing

Verified live:

- Dedicated `Supply Response Demo` workspace and `SupplyResponseDemo` SQL Database
  discovered and bound exactly
- Operational and analytics scripts applied twice without collisions; schema version
  12 is live
- Approval-gated live Fabric SQL integration test and health check passed
- `SupplyResponse` semantic model and report published to the dedicated workspace
- Fabric SQL OAuth2 data-source binding and live DAX query succeeded
- Both required report pages rendered their empty state without visual errors

Still required:

- Grant the deployed Container App managed identity the exact Fabric SQL database
  permissions through its separately approved deployment gate
- Run the approval-gated populated Power BI live consistency test after application deployment
- Verify refresh behavior, filters, and Decision ID parity against a live showcase case

### 5. Identity, Work IQ, Foundry, and live composition — tenant prerequisites configured; invocation gates pending

Tasks 14–17 implement the live case journey. Their local code and contract gates are complete; tenant-backed acceptance is not.

Completed implementation and tenant setup:

1. Implemented single-tenant Entra authentication and bound the stable Demo Personas:
   - `RL-PERSONA-ALEX` — Alex Morgan, Material Planner and Response Approver
   - `RL-PERSONA-JORDAN` — Jordan Lee, Quality Approver
   - `RL-PERSONA-TAYLOR` — Taylor Brooks, Finance Approver
2. Implemented cited supplier and Quality retrieval through Work IQ, including delegated OBO, bounded A2A parsing, source binding, and citation validation. The Work IQ service principal and exact delegated consent are configured in the tenant.
3. Implemented Foundry Agent Service and Microsoft Agent Framework orchestration while deterministic services retain decision authority. The three committed prompt-agent contracts are published and verified as immutable version `1` agents using `gpt-5.6-luna`.
4. Implemented the complete live Detect → Analyze → Decide → Execute → Observe composition with fail-closed readiness and Decision-linked lineage.
5. Created the fictional Work IQ Demo Corpus, verified the supplier email in Alex's mailbox and the Jordan-authored Quality post in Teams, recorded their deployment-specific source bindings, and verified the deterministic binding receipt.

Still required:

- Run the approval-gated Work IQ retrieval and verify both citations resolve to the accepted supplier and Quality sources.
- Invoke and evaluate the published Foundry agents through a separately approved live gate.
- Complete the remaining Fabric managed-identity grant and populated Power BI parity
  required by live readiness.
- Run deployed Entra authentication, Work IQ citation navigation, and the complete live browser journey.

Exit conditions include authenticated Alex approval/rejection, independently satisfied Quality and Finance prerequisites, navigable citations, and Decision-linked downstream work.

### 6. Deployment and release hardening — Azure application deployed; acceptance pending

Tasks 18–19 deploy the runtime to the personal `willmacdonald.com` tenant and prove the final contract. The Azure application infrastructure and immutable Container App image are deployed, the first revision is ready and running, and exact ACR, Key Vault, and Foundry RBAC assignments are verified. Fabric SQL identity access and the live acceptance journey remain.

- Provision the Azure application resources and configure deployment-specific bindings
- Deploy the API and web console, then connect them to the verified Fabric, Work IQ, Foundry, Entra, and Power BI prerequisites
- Verify live/fallback contract parity without mixing provenance
- Prove evidence conflict, staleness, citation, retry, and failure behavior
- Verify Demo Corpus privacy and the absence of real business data
- Meet the 90-second live-analysis target
- Complete the five core workflows within five minutes
- Rehearse a seven-to-ten-minute narrated demonstration
- Run both live and fallback recovery rehearsals

Final completion requires all 20 frozen acceptance criteria to pass. Local implementation alone is not sufficient for live-demo acceptance.

### Remaining deployment and acceptance gates

The Entra, Foundry, Fabric SQL, Work IQ Demo Corpus, and Power BI prerequisites
are configured and recorded in deployment-local storage. The remaining gates are:

1. Grant the deployed Container App managed identity exact Fabric SQL database access through its separate approval gate.
2. Verify the pinned Foundry agents and run the user-context-free live smoke check.
3. Run live Work IQ retrieval and the complete authenticated browser journey.
4. Load the showcase Case and verify Power BI refresh, filters, and Decision-ID parity against the application.

## Task-level status

| Task | Deliverable | Status |
|---:|---|---|
| 0 | Commit the frozen contract package | Complete |
| 1 | Canonical domain contracts and RL-001 template | Complete |
| 2 | Deterministic evaluation of every RL-001 Response Option | Complete |
| 3 | Evidence, approval, and analysis-version policy | Complete |
| 4 | Ranking and all ten evaluation cases | Complete |
| 5 | Runtime configuration and persistence ports | Complete |
| 6 | Immutable Decisions and transactional outbox | Complete |
| 7 | Exactly five actions and attempt history | Complete |
| 8 | Simulated Execution and Outcome Observations | Complete |
| 9 | Closed-loop application service | Complete |
| 10 | Progressive Case workspace | Complete |
| 11 | Complete fallback browser journey | Complete |
| 12 | Fabric SQL adapter and analytics views | Complete; live Fabric SQL setup, schema, idempotency, and health checks passed |
| 13 | Two-page Power BI project | Published; OAuth2 binding, DAX smoke query, and empty-state live render passed; populated parity pending |
| 14 | Single-tenant Entra authentication and persona roles | Complete locally; tenant configuration verified; deployed auth gate pending |
| 15 | Cited Microsoft 365 evidence through Work IQ | Complete locally; tenant consent, Demo Corpus sources, bindings, and receipt verified; live retrieval pending |
| 16 | Foundry-managed Agent Framework orchestration | Complete locally; three Luna agents published and verified; invocation/evaluation pending |
| 17 | Complete live Case journey | Complete locally; external readiness bindings and live browser gate pending |
| 18 | Personal-tenant provisioning and deployment | Azure application deployed with live Azure RBAC verified; Fabric SQL grant and post-deployment acceptance gates pending |
| 19 | Privacy, parity, failure, timing, and rehearsal gates | Planned |

## Backlog outside active acceptance

### Foundry IQ institutional knowledge

A future increment may retrieve SOPs, Supply and Quality policies, supplier-risk assessments, and continuity playbooks through a permission-aware cited knowledge base. This requires its own design review covering Azure AI Search, permissions, freshness, preview status, cost, typed constraint production, and fallback fixtures.

No Foundry IQ adapter, infrastructure, or acceptance criterion belongs in the active milestones until that increment is separately designed and approved.

### Optional Power BI expansion

Dedicated Exposure and Response Option Comparison pages may be considered after the two required pages pass live acceptance. The web decision console remains authoritative for case-level investigation and interaction.

### Non-blocking scale target

The original scale targets remain performance fixtures rather than correctness gates: 250 suppliers, 10,000 parts, 100,000 BOM relationships, multiple plants, 50,000 open customer-order lines, and twelve months of history.

## Definition of done

The project is ready for the final live demonstration only when:

- All frozen acceptance criteria pass.
- Runtime provenance remains immutable and visible.
- Live Work IQ, Fabric, Foundry, Entra, and Power BI paths are verified.
- Fallback remains explicit and cannot be mistaken for live success.
- Every approved Decision is durable and every downstream action and observation references it.
- No external supplier communication, purchase-order change, or financial commitment can occur.
- The Demo Corpus and deployed persona bindings pass the privacy review.
