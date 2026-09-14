# Supply Response

Supply Response is a decision-support demonstration for managing a fictional supplier disruption from detection through analysis, human approval, bounded execution, and outcome observation.

The project combines a deterministic supply-response core with a FastAPI application, a React decision console, durable SQLite or Fabric SQL persistence, and a Power BI project. Microsoft 365 and Azure integrations are added through explicit adapters so the complete live demonstration can use Work IQ, Microsoft Fabric, Microsoft Foundry, Microsoft Agent Framework, Entra ID, and Power BI without coupling the business logic to those services.

> **Live demo:** [Open Supply Response](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/). The latest verified release passed 364 web tests, production build, desktop/mobile browser checks, guarded Fabric/Foundry readiness, and live Alex acceptance. The current revision, immutable image, and release proof are recorded in the [deployment plan](.azure/deployment-plan.md).

## Current presenter journey

The live entry point is a presenter-controlled supplier-email check:

1. The presenter sends the fictional RL-001 disruption email from
   `will@willmacdonald.com` to Alex at `agent@willmacdonald.com`.
2. Alex selects **Check email for disruptions**. Work IQ searches Alex's mailbox
   for the approved scenario message; this is an explicit check, not continuous
   monitoring.
3. The page shows the actual sender, subject, received time, message text, and an
   Outlook link. Alex reviews the extracted delivery facts before continuing.
4. **Analyze this disruption** creates a source-bound case when necessary and
   runs or reopens its analysis. The email's stable mailbox-scoped identity
   prevents duplicate cases; changed or ambiguous content fails closed.
5. After the analysis loads successfully, the email-entry panel, saved-demo
   launcher, and recovery note disappear. The page continues directly into the
   analyzed case. The entry controls remain available if analysis fails so the
   presenter can retry.
6. The presenter compares traditional Power BI investigation with the five-stage
   AI-assisted workflow: **Understand the disruption**, **Investigate responses**,
   **Choose a response**, **Review and approve**, and **Execute mitigation plan**.

This path was live-verified as Alex using Will's `Demo run 0914-A` email. The
Outlook citation opened the exact message, and repeated analysis reopened the
same case and analysis. No outbound email, approval, or execution action was
performed during that acceptance.

## Current acceptance boundary

- **Live and accepted:** Alex sign-in; presenter-controlled Work IQ email
  discovery; reviewed email-to-case creation; duplicate prevention; live case
  analysis; Outlook citation; traditional Power BI investigation; exact
  card-to-report links; and the five-stage planner workspace.
- **Implemented and deployed, but not accepted with Taylor's real session:**
  separate Finance review, rejection/approval, and Alex's subsequent final
  decision for new cases whose spending exceeds $20,000.
- **Not yet a complete live demonstration:** option-specific mitigation
  execution, reviewed outbound email received by Will, populated execution
  outcomes in Power BI, and a reliable Teams desktop/web handoff still require
  end-to-end acceptance. Historical cases retain their saved approval policy.

The demo uses live Microsoft services with fictional business data. A healthy
deployment, a saved analysis, or a passing unit test does not by itself prove an
unaccepted cross-service step. See the [roadmap](docs/ROADMAP.md) for the detailed
status and remaining work.

## Presenting the comparison

For the complete story, start with **Check email for disruptions**. Reopen a
known analyzed case only when a repeatable walkthrough is preferable to a fresh
mailbox check. Reopening saved work does not retrieve sources again or approve a
response.

- **Explore in Power BI** starts a traditional investigation across 178 fictional
  operational records: inventory, deliveries, transfers, qualification, production
  demand and customer orders. The presenter uses rows, charts and filters to reason
  through the disruption.
- **Review with AI assistance** organizes the case into five stages from
  understanding the disruption through mitigation execution. Authoritative
  calculations and recommendation ranking remain deterministic; Finance review
  and Alex's final decision remain human actions.
- **A card's supporting-data link** opens the exact saved records used by that
  analysis—not the broad dataset or an unrelated case count. The inventory view
  reconciles 4,500 on hand − 200 held − 300 protected = 4,000 available components.

Follow the [traditional-versus-assisted presenter walkthrough](docs/demo/traditional-and-assisted-walkthrough.md).
Real services host fictional data. A saved snapshot, successful source check or
working citation is not proof of a fresh retrieval during the presentation.

## What the demo shows

The canonical `RL-001` Demo Template targets the following closed-loop story.
The downstream steps are implemented locally but are not all accepted in the live tenant:

1. **Detect** — retrieve and structure a fictional supplier signal with source evidence.
2. **Analyze** — calculate inventory, production, customer, revenue, margin, and OTIF exposure deterministically.
3. **Decide** — compare feasible Response Options, recommend one using thresholded lexicographic ranking, and let Alex Morgan approve or reject it.
4. **Execute** — preserve the immutable Decision, create five bounded Execution Actions, and explicitly start visibly labeled Simulated Execution.
5. **Observe** — append Simulated Observations and compare predicted and observed results in the web console and, in live mode, Power BI.

Business personas, suppliers, communications, orders and outcomes are fictional.
Canonical scenario identities use `RL-`; the wider reporting context also uses
explicitly fictional `RPT-` identities.

## Architecture

```mermaid
flowchart LR
    WI[Work IQ] --> ADAPTERS[Integration adapters]
    FAB[Fabric SQL] --> ADAPTERS
    SYN[Synthetic evidence] --> ADAPTERS
    SQLITE[SQLite] --> ADAPTERS

    ADAPTERS --> ORCH[Foundry-hosted or local orchestration]
    ORCH --> API[FastAPI application boundary]
    API --> CORE[Deterministic decision core]
    CORE --> ANALYSIS[Immutable Analysis Version]
    ANALYSIS --> WEB[React decision console]
    WEB --> DECISION[Immutable Decision]
    DECISION --> OUTBOX[Transactional outbox]
    OUTBOX --> ACTIONS[Bounded Execution Actions]
    ACTIONS --> OUTCOMES[Outcome Observations]
    OUTCOMES --> WEB
    ANALYSIS --> SAVED[Exact saved supporting records]
    SAVED --> PBI[Power BI supporting-data pages]
    REPORTING[Fictional operational reporting snapshot] --> TRAD[Traditional Power BI tables and charts]
    DECISION --> PBI
    OUTCOMES --> PBI
```

The Decision is the immutable pivot between analysis and downstream activity. Authoritative calculations, feasibility, ranking, and approval policy remain in deterministic services rather than an LLM or agent.

## Implemented capabilities

- Canonical domain contracts for Case Instances, Evidence Items, Analysis Versions, Response Options, Decisions, Execution Actions, attempts, and Outcome Observations.
- Deterministic `RL-001` data, exposure calculations, option evaluation, Approval Satisfaction, and thresholded lexicographic ranking.
- Integrated validation for all ten focused `RL-EVAL-*` cases.
- Append-only, idempotent Decisions and transactional outbox processing.
- Exactly five bounded Execution Actions with durable attempt history.
- Explicit, idempotent Simulated Execution with permanently labeled observations.
- Presenter-focused React workspace with a reviewed email entry, five stage tabs,
  source links/icons, bottom-of-card provenance, whole-dollar USD totals,
  two-decimal unit prices, immediate option-selection feedback, and an accessible
  recommendation explanation sheet.
- Durable fallback persistence through SQLite and a complete browser end-to-end gate.
- Opt-in Fabric SQL persistence, Entra token authentication, schema health checks, and read-only analytics views.
- Guarded, insert-only canonical RL-001 source loading with full stored-data readback and timezone-preserving SQL binding. Live retrieval freshness is separate from fictional business dates, so the corpus does not require daily regeneration. See the [loader procedure](docs/deployment/personal-tenant.md#load-the-canonical-rl-001-operational-source).
- A published DirectQuery Power BI project with seven broad traditional pages and eight exact saved-context pages. The isolated reporting dataset contains 178 records without changing saved analyses or the canonical operational source. Native tables/charts/filter checks, current/older saved inventory and order parity, and mismatched-identity safeguards passed. Artifact-bound acceptance enables the website links; populated execution outcomes remain unverified.
- Single-tenant Entra authentication with exact Alex/Taylor identity and role bindings. Authenticated Finance inbox/detail and approve/reject routes are deployed. Alex's real session passed; Taylor's interactive acceptance awaits password sign-in. No replacement identity or new permission was created.
- A delegated Work IQ OBO client and bounded MCP integration with strict
  source-statement validation. The live presenter action discovers the approved
  supplier email, reads that individual message, validates its source facts and
  citation, and binds it to an idempotent case. Named Team/channel discovery uses
  the same structured Work IQ path. This is structured discovery, not Copilot
  semantic search; the application has no direct Graph client. Configured message
  IDs validate results and are never lookup inputs or fallback fetch targets. The
  supplier-email path is accepted; the Teams handoff/authentication-loop report
  remains unresolved.
- Microsoft Agent Framework orchestration that preserves deterministic decision authority, plus fail-closed Foundry publication and verification tooling.
- Three immutable Foundry prompt agents—signal, context, and decision—published as version `1` and verified against their committed contracts on `gpt-5.6-luna`.
- Personal-tenant Azure infrastructure deployed in East US 2 through the guarded
  workflow. Revision35 is healthy with unchanged reporting activation,
  resource-scoped roles and scale. The current release verified the actual
  email-to-analysis transition without creating a duplicate case or performing
  an outbound email, approval, or operational action.

Live Microsoft service integration is not yet complete. Published or configured cloud prerequisites do not count as live acceptance until their approval-gated invocation, data, browser, and cross-service consistency gates pass. The [roadmap](docs/ROADMAP.md) records the verified boundary between implemented, configured, and pending work.

## Runtime modes

Each Case Instance has exactly one immutable runtime mode. State never merges implicitly between modes.

| Mode | Purpose | Persistence | Integrations |
|---|---|---|---|
| `fallback` | Local development, automated tests, rehearsals, and cloud-outage recovery | SQLite | Synthetic evidence and local orchestration; Power BI unavailable |
| `live` | Final demonstration acceptance | Fabric SQL | Entra ID, Work IQ, Fabric, Foundry Agent Service, Microsoft Agent Framework, and Power BI |

Fallback mode is always explicit and never counts as proof that a live integration passed. Business data remains fictional in both modes.

## Repository layout

```text
supply-response/
├── apps/
│   ├── api/                 # FastAPI application and HTTP contracts
│   └── web/                 # React/Vite decision console
├── data/
│   ├── domain/              # Canonical domain models
│   ├── schemas/             # Portable source-data schemas
│   └── synthetic/           # Deterministic Demo Corpus generation
├── services/
│   ├── analysis/            # Exposure, options, ranking, and analysis
│   ├── decisions/           # Decision and outbox application services
│   ├── execution/           # Action planning, workers, and playback
│   ├── persistence/         # SQLite/Fabric persistence contracts
│   └── policy/              # Evidence, approval, and threshold policies
├── integrations/fabric/     # Fabric configuration, schema, and health
├── fabric/
│   ├── sql/                 # Operational schema and analytics views
│   └── power-bi/            # Power BI Project (PBIP)
├── evaluations/             # Focused cases and frozen expected results
├── tests/                   # Unit, contract, integration, and live gates
├── docs/                    # Architecture, ADRs, specs, plans, and roadmap
└── scripts/                 # Local verification entry points
```

## Local development

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Chromium installed through Playwright for browser tests
- ODBC Driver 18 for SQL Server only when using live Fabric SQL

### Install

From the repository root:

```bash
uv sync --python 3.12
npm --prefix apps/web ci
(cd apps/web && npx playwright install chromium)
```

### Run the fallback application

Start the API:

```bash
export SUPPLY_RESPONSE_RUNTIME_MODE=fallback
export SUPPLY_RESPONSE_DATABASE_URL=sqlite:///./supply-response.db
uv run --python 3.12 uvicorn apps.api.app.main:app --reload
```

In another terminal, start the web console:

```bash
npm --prefix apps/web run dev
```

Open `http://localhost:5173`. The API is available at `http://localhost:8000`, with OpenAPI documentation at `http://localhost:8000/docs`.

### Verify the fallback journey

After installing the dependencies and Playwright Chromium, run:

```bash
scripts/run_fallback_demo.sh
```

This gate runs the Python suite, Vitest suite, production web build, and real-browser fallback tests against a fresh temporary SQLite database. It does not require or contact Microsoft cloud services.

Individual checks are also available:

```bash
uv run --python 3.12 pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

## Live integration safety

Live mode fails closed when configuration, identity, connectivity, or schema validation is incomplete; it never silently falls back to SQLite. Tenant IDs, Entra object IDs, UPNs, workspace IDs, database endpoints, and other deployment bindings must remain in environment-specific configuration rather than committed source.

Cloud deployment and live tests are intentionally approval-gated because they authenticate to external services and may create or modify tenant resources. Deployment guidance, verified cloud evidence, remaining bindings, and required settings are recorded in [the personal-tenant deployment plan](.azure/deployment-plan.md), the implementation plan, and the task reports under `.superpowers/sdd/`.

## Project documentation

- [Frozen demo contract](docs/superpowers/specs/2026-08-30-supply-response-demo-contract-design.md) — controlling product scope and acceptance criteria
- [Original implementation plan](docs/superpowers/plans/2026-08-30-supply-response-demo-implementation.md) — Tasks 0–19
- [Approved traditional reporting correction](docs/superpowers/specs/2026-09-12-traditional-operational-reporting-design.md) — traditional investigation versus exact supporting-data links
- [Presenter header and planning tabs](docs/superpowers/specs/2026-09-12-presenter-header-and-stage-tabs-design.md)
- [Recommendation explanation sheet](docs/superpowers/specs/2026-09-12-recommendation-explanation-sheet-design.md)
- [Email-to-mitigation presenter journey](docs/superpowers/specs/2026-09-12-email-to-mitigation-workflow-design.md)
- [Reviewed email-to-case release evidence](docs/reviews/2026-09-14-email-to-case-release.md)
- [Roadmap and current status](docs/ROADMAP.md)
- [Canonical domain language](CONTEXT.md)
- [Architecture decisions](docs/adr/)
- [Portable-core architecture](docs/architecture/portable-core.md)
- [Current acceptance traceability](docs/current-baseline-and-acceptance-traceability.md)
- [Original project brief](Supply-Response-Project-Brief.md) — product vision; the frozen contract controls when they differ

## Scope boundaries

The project does not send supplier communications, modify purchase orders, make financial or contractual commitments, use real business data, or permit an agent to perform authoritative arithmetic. Fabric IQ is optional for the core demonstration. Foundry IQ retrieval of SOPs, policies, supplier-risk documents, and continuity playbooks remains a separately designed backlog item.
