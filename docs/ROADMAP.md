# Supply Response Roadmap

## September 14 repeatable presenter runs — locally verified; release pending

Implemented and locally verified: every successful **Check email for
disruptions** response receives a server-issued Presenter Run identity, and
**Analyze this disruption** creates a fresh source-bound Case Instance for that
run. Reusing the same marked email therefore does not inherit Taylor's approval,
Alex's Decision, execution state, drafts, playbacks, or outcomes. Retries and
concurrent requests within one Presenter Run remain idempotent.

Server-side retention keeps the current presenter case and the three most recent
historical presenter cases. It prunes only complete aggregates for live,
showcase, supplier-email-bound cases; automated-test, fallback, unbound showcase,
operational-source, and traditional-reporting data are outside the retention
set. The case-header **Open case dashboard** link is removed while **Explore in
Power BI** and exact supporting-data links remain.

Local feature evidence is green: 117 presenter/API/persistence tests and 369 web
tests passed, the production web build passed, and the changed production Python
files passed focused Ruff and Pyright checks. The repository-wide Python suite
still has its previously recorded unrelated diagnostics/schema-count/reporting-
digest failures; repository-wide Ruff and Pyright are also not clean. Exact
results are in the [repeatable presenter-run release record](reviews/2026-09-14-repeatable-presenter-runs.md).

The default, read-only live cleanup preview found one eligible retained presenter
case and no cases proposed for pruning. No cleanup was applied. Deployment and
live browser acceptance remain pending: after deployment, rerun the preview,
apply only that exact reviewed plan with separate authorization, then prove two
consecutive checks of the same email create different Case IDs and that the
second run waits for a new Taylor review.

## September 14 email-to-case increment — deployed and live-verified

Implemented: actual email review → explicit case creation → existing analysis
using that bound email. Atomic duplicate prevention uses the existing case
transaction and immutable source JSON, not a new database or migration.
Work IQ's stable email lookup passed an Inbox/Archive/Inbox move test. Desktop
and mobile presenter interaction, 360 web tests and build pass. Independent
review found no blocking issues. Revision 33 (`974d4a1`) passed live case creation,
analysis, exact Outlook citation and duplicate retry acceptance as Alex using
Will's 0914-A email. Backend checks: 661 passed, 18 live-setting skips. See
[release evidence](reviews/2026-09-14-email-to-case-release.md).
No outbound email or Finance decision is part of this increment.

## Earlier September 14 inbox-check increment

Implemented and locally verified: **Check email for disruptions** → Work IQ
mailbox discovery → validated supplier email preview and Outlook citation.
Only Alex may check; sender is Will, recipient is Alex, and the message must
match the approved scenario markers. No email is sent or case created by a check.
Deployed as revision32 (`736c339`); Alex's real browser found and read Will's
new `Demo run 0914-A` email through Work IQ on September 14. Prior release notes
below remain historical. Next: bind a reviewed message to a new case atomically with
duplicate prevention, then continue the existing analysis/approval journey.

**Last updated:** September 14, 2026 (America/Chicago).
**Deployed baseline:** website revision **ca-sr-demo--0000037**, deployed source
`afa688a`; unchanged reviewed report/model artifacts through `fd53e99`.

This roadmap distinguishes implemented code, configured identities, verified live
behavior and work still missing. The September 12 release was deployed from
`codex/planner-experience`; deployment is not a claim that the branch was merged.

## What is live now

[Open the demo](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/).

- Presenter header **Respond to supply disruptions with AI**, followed by five
  tabs: **Understand the disruption**, **Investigate responses**, **Choose a response**,
  **Review and approve**, **Execute mitigation plan**.
- Independent Alex/Taylor approval workflow for new cases. Taylor's real browser
  displayed the exact reviewed evidence, recorded the Finance approval, and
  returned through the Microsoft account picker to Alex's exact response on tab
  4. Alex's final-approval control was visible but intentionally not submitted.
  Independent execution/email remain unavailable.
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
| Alex identity | Interactive app sign-in verified | Fresh live analysis and Finance submission passed; revision37 handoff returned from Taylor to Alex's exact response on tab 4 |
| Jordan and Taylor identities | Existing tenant identities/roles retained | Exact Taylor app binding and real Taylor browser approval passed; no identity or permission replacement |
| Finance review | Interactive workflow deployed and accepted through handoff | Taylor reviewed the exact proposal evidence, approved it, and returned to Alex's final-approval screen. Alex's final approval was intentionally not submitted |
| Foundry | Agents published and contract/readiness checks passed | Optional explanation invocation/evaluation remains a separate gate |
| Complete live journey | Not complete | Taylor approval and handoff are accepted; Alex's final approval, bounded downstream actions/observations and cross-service outcome parity remain unverified |

## Remaining work

### Latest accepted milestone — Taylor → Alex handoff

September 14: the authenticated Finance presentation and handoff corrections are
deployed from source `afa688a` on revision `ca-sr-demo--0000037`. Fresh validation
passed 369 web tests, the TypeScript/Vite production build, API and Finance tests,
58 infrastructure tests, Ruff, and diff checks.

In Taylor's real browser, the reviewed response showed both Fabric records as
retrieved for the analysis with required checks passed. Taylor's completed
approval offered **Return to Alex for final approval**. After the Microsoft
account picker, Alex returned to the exact case, analysis, and combined response
on tab 4 with Taylor's approval time and **Give final Alex approval** visible.
No console warning or error appeared. Alex's final approval was intentionally
not submitted. The controlling proof is the [Taylor evidence and Alex handoff
deployment record](../.azure/deployment-plan.md#taylor-evidence-and-alex-handoff-release--2026-09-14).

The earlier [September 13 approval release](reviews/2026-09-13-approval-browser-release.md)
records the historical pre-acceptance checkpoint. It is not the current live
status. The reviewed additive Finance SQL upgrade preserved saved
case/analysis/decision payload hashes and added no grants.

Independent decisions are saved without launching the legacy combined-response
execution planner. Pending work is retained but not claimed, and the UI clearly
says execution is unavailable for this milestone. The next visible gates are
Alex's final approval, option-specific execution, a reviewed email from Alex to
Will, and deployment plus two-run browser acceptance of repeatable Presenter
Runs. Test counts alone do not close any of these live acceptance gates.

The following September 13 increment notes are a historical snapshot superseded
by the September 14 increments and revision 37 acceptance above. They do not
describe current local or deployed status.

The proposed [email-to-mitigation presenter journey](superpowers/specs/2026-09-12-email-to-mitigation-workflow-design.md)
captures the next integrated increment: Will's real mailbox as Supplier Alpha,
presenter-controlled Work IQ discovery, five stages, independent Taylor review,
option-specific plans, and an explicitly reviewed real email back to Will.
At that checkpoint its written design was approved, but none of those additions
was yet claimed as deployed. The current acceptance boundary is recorded above.
Historical cases keep their original evidence.

September 13 local progress: independent Finance rules, durable review history,
versioned case policy, current-proposal storage, submission/review commands,
current/historical queries, proposal-bound final Decisions and safeguards on
individual execution actions have passed independent review. The current
checkpoint passes 497 backend tests (11 intentional skips, 15 live tests
excluded). Queued planning and simulated playback safeguards remain separate
unfinished increments. Five-stage navigation
passes 331 frontend tests, the production build, and local desktop/phone browser
checks. At that checkpoint Taylor's authenticated inbox, application-route
integration and the new email workflow were not connected or enabled; see the
[increment evidence and remaining gates](reviews/2026-09-13-email-workflow-progress.md).

### 1. Finance-person review follow-through

Taylor Brooks (`RL-PERSONA-TAYLOR`) already has a separate Finance Approver
identity and tenant role assignment. Reuse that identity; do not create a
replacement or present an Alex click as Taylor's approval.

The deployed workflow now enforces Taylor's independent identity, binds her
review to the exact analysis and response, records the outcome, and returns to
Alex's exact final-approval screen. That journey is live-accepted through the
handoff. Alex's final approval was deliberately not submitted during acceptance,
so final Decision and downstream execution remain separate pending gates. Any
new tenant permission or role change remains an explicit approval boundary.

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
- Bounded presenter-history retention and a preview-first cleanup command are
  locally implemented. The first live preview proposed no deletions. Deployment,
  an exact reviewed non-empty preview if older eligible cases later exist, and
  separately authorized application remain pending; never broaden the cleanup to
  automated-test, fallback, unbound showcase, operational-source, or reporting
  records.
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
- [Repeatable presenter runs](superpowers/specs/2026-09-14-repeatable-presenter-runs-design.md)
- [Repeatable presenter-run implementation](superpowers/plans/2026-09-14-repeatable-presenter-runs.md)
- [Repeatable presenter-run release evidence](reviews/2026-09-14-repeatable-presenter-runs.md)
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
