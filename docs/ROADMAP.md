# Supply Response Roadmap

## September 14 email-to-case increment — release verification

Implemented: actual email review → explicit case creation → existing analysis
using that bound email. Atomic duplicate prevention uses the existing case
transaction and immutable source JSON, not a new database or migration.
Work IQ's stable email lookup passed an Inbox/Archive/Inbox move test. Desktop
and mobile presenter interaction, 360 web tests and build pass. Independent
review, deployment and live creation/analysis acceptance are still pending.
No outbound email or Finance decision is part of this increment.

## September 14 inbox-check increment

Implemented and locally verified: **Check email for disruptions** → Work IQ
mailbox discovery → validated supplier email preview and Outlook citation.
Only Alex may check; sender is Will, recipient is Alex, and the message must
match the approved scenario markers. No email is sent or case created by a check.
Deployed as revision32 (`736c339`); Alex's real browser found and read Will's
new `Demo run 0914-A` email through Work IQ on September 14. Prior release notes
below remain historical. Next: bind a reviewed message to a new case atomically with
duplicate prevention, then continue the existing analysis/approval journey.

**Last updated:** September 13, 2026 (America/Chicago).
**Deployed baseline:** website revision **ca-sr-demo--0000029**, deployed source
`afbf8db`; unchanged reviewed report/model artifacts through `fd53e99`.

This roadmap distinguishes implemented code, configured identities, verified live
behavior and work still missing. The September 12 release was deployed from
`codex/planner-experience`; deployment is not a claim that the branch was merged.

## What is live now

[Open the demo](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/).

- Presenter header **Respond to supply disruptions with AI**, followed by five
  tabs: **Understand the disruption**, **Investigate responses**, **Choose a response**,
  **Review and approve**, **Execute mitigation plan**.
- Independent Alex/Taylor approval workflow for new cases. Real Alex creation,
  analysis and Finance submission passed; Taylor password sign-in is needed to
  finish live acceptance. Independent execution/email remain unavailable.
- Vertically arranged, planner-language cards with source details at the bottom,
  email/Teams icons, whole-dollar USD totals and two-decimal per-part costs.
- **Click here to understand why** opens the recommendation explanation sheet.
  Recommendation, human approval and execution remain different steps.
- Seven traditional Power BI pages: **Supply overview**, **Inventory**,
  **Supplier deliveries**, **Plant transfers**, **Supplier qualification**,
  **Customer orders**, **Production demand**. They lead with rows, charts and
  filters across 178 fictional operational records—not copies of the AI cards.
- Separate card links open exact saved inventory, shipment, transfer,
  qualification, customer-order and response-option context. Reporting activation
  is enabled only for the accepted artifact.
- Existing saved cases can be reopened without creating another case or refreshing
  evidence. A fresh showcase case/analysis is a separate operation.

The traditional reporting snapshot is isolated in the existing Fabric SQL
database. It did not replace the canonical operational source or modify saved
cases/analyses. Exact saved evidence never falls back to wider reporting data.

## Verified release boundary

The September 12 [reporting release evidence](reviews/2026-09-12-traditional-reporting-verification.md)
records native Power BI inspection as Alex, actual deployed website checks,
SQL-to-model parity, publication review, negative identity checks and deployment.

- Native broad pages show rows/charts; Chicago/component filtering changes the
  inventory view to 4,500 on hand − 200 held − 300 protected = 4,000 usable.
- Exact current and older saved inventory/order views were checked. The live
  website's inventory, order and shipment destinations match its saved analysis.
  Two affected order lines are $375,000 and $580,000; Alpha's proposed partial
  shipment is 3,000 units on September 6 at $7.50 per unit.
- Unknown/mismatched selections remain unavailable rather than showing another
  case's values. The historical inventory gap was a DAX measure defect, not absent
  records in the inspected analysis.
- Final release regression: 187 Fabric tests passed (one optional live test
  skipped), 326 frontend tests and production build passed, and 98 deployment/
  activation tests passed. Actual SQL-engine and native-model checks are recorded
  separately; unit tests are not treated as native acceptance.
- Revision28 is Healthy/Running with 100% traffic; scale 0–2 and the same three
  resource-scoped Azure roles are unchanged. Live Fabric/Foundry readiness passed.
  No case, analysis, Decision, approval, simulation or execution was created by
  this release verification.

The release reused saved evidence. It does not prove a fresh Work IQ retrieval,
Foundry explanation invocation, finance-person approval or downstream execution.

## Current capability status

| Area | Status | Boundary |
|---|---|---|
| Domain, deterministic calculations and ranking | Implemented and tested | RL-001 and ten focused evaluation cases; AI does not own arithmetic or approval |
| Durable backend and fallback journey | Implemented and locally verified | Immutable Decisions, outbox, five bounded actions, simulated observations; not equivalent to live downstream acceptance |
| Planner website | Deployed and inspected as Alex | Header, tabs, currency, source links and explanation sheet verified on an existing saved case |
| Fabric SQL | Live and verified | Schema12, canonical source, saved projections and isolated 178-record reporting dataset |
| Power BI | Traditional and exact-source reporting published and accepted | Native rows/charts/filtering and selected current/older evidence parity; populated execution outcomes and within-case multi-version history are not certified |
| Work IQ | Prior structured discovery/read/validation passed | Work IQ entity tools discover sources and read individual messages; configured IDs validate results, not lookup inputs. No direct Graph fallback. This release did not repeat discovery |
| Alex identity | Interactive app sign-in verified | Fresh live analysis and Finance submission passed on revision29 |
| Jordan and Taylor identities | Existing tenant identities/roles retained | Exact Taylor app binding deployed; real Taylor password sign-in still needed |
| Finance review | Interactive workflow implemented and deployed, acceptance incomplete | New cases use explicit Taylor review; old cases retain standing authorization. No real Taylor approve/reject or Alex final approval verified yet |
| Foundry | Agents published and contract/readiness checks passed | Optional explanation invocation/evaluation remains a separate gate |
| Complete live journey | Not complete | Live human approval, bounded downstream actions/observations and cross-service outcome parity remain unverified |

## Remaining work

### Active delivery milestone — Alex → Taylor → Alex

September 13: authenticated routes and browser screens are connected, reviewed
and deployed on revision29. Alex's real sign-in, new case, live analysis and
$24,750 submission passed. The request is waiting for Taylor; her separate
Microsoft password sign-in is the current blocker. See the
[release and exact resume links](reviews/2026-09-13-approval-browser-release.md).
Local two-page browser verification covers Alex submitting, Taylor rejecting,
Alex resubmitting, Taylor approving and Alex finalizing, with wide/phone layouts.
Those browser responses are simulated; real separate Microsoft-account acceptance
for Taylor on the deployed site is still pending. Current checks: 346 frontend tests/build;
561 backend/API/auth/Finance/execution/persistence/deployment tests, 11 skips.
The reviewed additive Finance SQL upgrade has been applied with identical saved
case/analysis/decision payload hashes before and after. No grants were added.

Independent decisions are saved without launching the legacy combined-response
execution planner. Pending work is retained but not claimed, and the UI clearly
says execution is unavailable for this milestone. Next visible milestone is a
reviewed email from Alex to Will, followed by presenter-controlled inbound email
discovery. Test counts alone do not close any of these live acceptance gates.

The following September 13 increment notes describe earlier checkpoints, not the
current local implementation status.

The proposed [email-to-mitigation presenter journey](superpowers/specs/2026-09-12-email-to-mitigation-workflow-design.md)
captures the next integrated increment: Will's real mailbox as Supplier Alpha,
presenter-controlled Work IQ discovery, five stages, independent Taylor review,
option-specific plans, and an explicitly reviewed real email back to Will.
Its written design was approved September 13; none of these additions is claimed as
deployed by this roadmap update. Historical cases keep their original evidence.

September 13 local progress: independent Finance rules, durable review history,
versioned case policy, current-proposal storage, submission/review commands,
current/historical queries, proposal-bound final Decisions and safeguards on
individual execution actions have passed independent review. The current
checkpoint passes 497 backend tests (11 intentional skips, 15 live tests
excluded). Queued planning and simulated playback safeguards remain separate
unfinished increments. Five-stage navigation
passes 331 frontend tests, the production build, and local desktop/phone browser
checks. Taylor's authenticated inbox, application-route integration and the new
email workflow are not connected or enabled yet; see the
[increment evidence and remaining gates](reviews/2026-09-13-email-workflow-progress.md).

### 1. Separate finance-person review workflow

Taylor Brooks (`RL-PERSONA-TAYLOR`) already has a separate Finance Approver
identity and tenant role assignment. Reuse that identity; do not create a
replacement or present an Alex click as Taylor's approval.

The deployed composition currently configures only Alex's interactive persona
binding and supplies Taylor's predefined RL-001 standing authorization. It has
no Taylor sign-in/review inbox/case-specific approve-or-reject workflow. This is
missing implementation, not merely a hidden link or a pending test.

The next finance increment must make the planner-to-finance handoff visible,
enforce the independent identity and role, bind the review to the exact analysis
and response, record the outcome, and return meaningful status to the planner.
Review and verify that journey separately from Alex's final Decision. Any new
tenant permission or role change remains an explicit approval boundary.

### 2. Teams source opening and session behavior

The user previously opened the exact Quality post, but later reported that the
link did not use the already-open Teams app and that the browser looped through
authentication. The UX/reporting release did not fix or certify this behavior.

Reproduce the actual browser-to-Teams handoff as Alex, distinguish link correctness
from desktop association and browser authentication, and verify a usable presenter
path to the exact Jordan-authored post. Do not infer success from the source URL
or a provisioned Teams identity alone.

### 3. Finish live approval and downstream acceptance

Retain the existing fail-closed policy and immutable lineage while verifying:

- Independently satisfied Quality and Finance prerequisites and Alex's final
  approval/rejection against the intended Analysis Version.
- The approved Decision, its five linked bounded actions, and ten permanently
  labeled simulated observations.
- Populated Power BI Decision/action/outcome parity for that same case.
- Within-case analysis-version history, optional Foundry explanation invocation
  and evaluation, and live/fallback recovery.
- Privacy, failure, retry, citation, timing and narrated rehearsal gates from the
  controlling contract. Do not claim the 90-second analysis or five-minute
  workflow targets without measurement.

### 4. Presenter usability follow-through

- Power BI DirectQuery charts can load noticeably later than row grids; profile
  this before claiming a smooth timed presentation.
- Browser automation did not expose a new tab after one target-blank click.
  Exact emitted links were separately rendered and verified; automatic app/browser
  handoff is not certified by that result.
- The user requested a way to clean up unfamiliar test cases. No case deletion
  or delete workflow shipped in this release. Resolve exact targets and choose a
  recoverable cleanup design before removing data.
- Rehearse the [traditional-versus-assisted walkthrough](demo/traditional-and-assisted-walkthrough.md)
  using a known saved case; keep broad fictional context distinct from exact
  supporting evidence and avoid unmeasured productivity claims.

## Controlling guidance and history

The [frozen demo contract](superpowers/specs/2026-08-30-supply-response-demo-contract-design.md)
defines the original closed-loop acceptance. Later approved guidance controls
the specific presenter and reporting corrections:

- [Planner experience delivery history](superpowers/plans/2026-09-08-planner-experience-delivery.md)
- [Presenter header and three planning tabs](superpowers/specs/2026-09-12-presenter-header-and-stage-tabs-design.md)
- [Recommendation explanation sheet](superpowers/specs/2026-09-12-recommendation-explanation-sheet-design.md)
- [Traditional operational reporting correction](superpowers/specs/2026-09-12-traditional-operational-reporting-design.md)
- [Traditional reporting implementation and reviews](superpowers/plans/2026-09-12-traditional-operational-reporting.md)
- [Deployment and live acceptance proof](../.azure/deployment-plan.md)
- [Prior Work IQ discovery result](deployment/workiq-discovery-integration-result.md)

The [original Tasks 0–19 plan](superpowers/plans/2026-08-30-supply-response-demo-implementation.md)
and dated verification reports retain historical test counts and checkpoints.
An old “pending” statement is not current release status; conversely, a newer UX
release does not certify unrelated downstream gates.

## Backlog outside active acceptance

**Foundry IQ institutional knowledge:** SOPs, policies, supplier-risk assessments
and continuity playbooks require a separate design covering permissions,
freshness, retrieval, cost and typed constraints. No new infrastructure or
acceptance criterion is implied by this backlog.

**Scale fixtures:** 250 suppliers, 10,000 parts, 100,000 BOM relationships, multiple
plants, 50,000 open customer-order lines and twelve months of history remain
future performance fixtures—not claims about the 178-record reporting dataset.

## Definition of done

A final end-to-end live demonstration requires all applicable acceptance gates:
verified service paths and independent human approvals; immutable runtime/source
provenance; durable Decision-linked actions and observations; explicit simulation
and fallback labels; privacy review; and actual presentation/recovery rehearsal.
No external supplier communication, purchase-order change or financial commitment
is authorized by the demonstration. A healthy deployment alone is not completion.
