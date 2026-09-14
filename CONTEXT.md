# Supply Response

Supply Response is the domain of evaluating a supply disruption, recording a human response decision, and observing the bounded work and results that follow from that decision.

## Language

**Disruption Case**:
A tracked supply disruption whose evidence, analyses, decisions, execution actions, and outcome observations share one runtime-mode provenance.
_Avoid_: Run, incident run

**Demo Template**:
A reusable, deterministic fictional disruption story with fixed inputs and expected behavior. `RL-001` is the canonical Demo Template.
_Avoid_: Disruption Case, evaluation case

**Case Instance**:
One immutable instantiation of a Demo Template for an automated test, rehearsal, or showcase presentation.
_Avoid_: Demo Template, resettable run

**Analysis Version**:
An immutable assessment of a Disruption Case at a particular point in its evidence and operational state.
_Avoid_: Analysis run, current analysis

**Saved Supporting Records**:
The operational records captured for a particular Analysis Version and used to substantiate its quantities, dates and calculated impacts. Broader or newer records are not substitutes for these records.
_Avoid_: Current inventory, latest data, unrelated case summary

**Traditional Investigation**:
A planner's examination of operational rows, charts and filters to connect supplier deliveries, inventory, production demand, customer exposure and response possibilities.
_Avoid_: AI answer dashboard, recommendation walkthrough

**Operational Reporting Snapshot**:
A fixed collection of fictional operational records providing wider business context for Traditional Investigation. It is distinct from the Saved Supporting Records of an individual Analysis Version.
_Avoid_: Live ERP feed, historical analysis evidence

**AI-Assisted Review**:
A planner's review of the disruption, cited communications, operational evidence, calculated impacts and response choices brought together for a Disruption Case. Assistance does not transfer calculation or approval authority to the AI.
_Avoid_: Autonomous decision, automatic approval

**Current Supplier — RL-Supplier Alpha**:
The fictional supplier whose disrupted delivery initiates the canonical RL-001 case and who proposes a partial shipment.
_Avoid_: Alpha without a supplier label, person

**Alternate Supplier — RL-Supplier Beta**:
The fictional alternative supplier whose qualification must be checked before its proposed supply can be used.
_Avoid_: Beta without a supplier label, person, approved supplier

**Response Option**:
An evaluated alternative that Alex may select when making a Decision.
_Avoid_: Scenario, selected action, response action

**No-Mitigation Baseline**:
The calculated consequences of allowing the disruption to proceed without an active mitigation. It is a comparison point and does not count as a feasible mitigation.
_Avoid_: Feasible scenario, recommended response

**Feasible Mitigation**:
A Response Option that satisfies the operational, evidence, qualification and planning-policy constraints for consideration. Feasibility does not grant spending authority or replace required Prerequisite Approvals and the final Decision.
_Avoid_: Approved response, available scenario, possible response

**Uncovered Constrained-Part Demand**:
The quantity of the disrupted component still required by customer demand that a Response Option does not protect.
_Avoid_: Uncovered customer-demand quantity, finished-goods demand

**Projected OTIF Loss Percentage**:
The percentage of customer-order lines affected in an Analysis Version that remain projected late after applying a Response Option.
_Avoid_: OTIF lines at risk, overall OTIF

**Protected Customer Order**:
An affected customer-order line whose complete quantity remains deliverable on time after applying a Response Option.
_Avoid_: Partially protected order, allocated order

**Thresholded Lexicographic Ranking**:
A policy that evaluates Response Options through an ordered series of comparators, retaining options within each comparator's materiality threshold before evaluating the next comparator.
_Avoid_: Weighted score, pairwise tolerance ranking

**Recommended for Review**:
A Response Option retained by the planning policy recorded for an Analysis Version and presented for human consideration. Its recommendation is neither approval nor evidence of execution, and predicted benefits remain predictions.
_Avoid_: AI-approved response, executed response, guaranteed outcome

**Analysis Horizon**:
The fixed period from a disruption's effective date through the latest due date among the affected production and customer orders assessed in an Analysis Version.
_Avoid_: Rolling window, scenario horizon

**Scenario Effective Time**:
The visible business time at which a Demo Corpus case is evaluated. It is distinct from the wall-clock time when sources are retrieved.
_Avoid_: Current time, retrieval time

**Evidence Retrieval Time**:
The wall-clock time a source was retrieved for an Analysis Version. Reopening that analysis does not make the retrieval new or establish when every underlying operational record was last updated.
_Avoid_: Scenario date, current freshness, last ERP update

**Evidence Item**:
A source-backed operational fact, source statement, Prerequisite Approval, or contextual item used to understand a Disruption Case.
_Avoid_: Evidence reference, citation string

**Authority Scope**:
The specific facts that an Evidence Item is qualified to establish.
_Avoid_: Source priority, universal authority

**Evidence Conflict**:
A disagreement between Evidence Items about a fact relevant to analysis, feasibility, or approval.
_Avoid_: Agent uncertainty, stale evidence

**Conflict Resolution**:
An authorized, source-backed determination of which value governs an Evidence Conflict and why.
_Avoid_: Agent judgment, inferred resolution

**Decision**:
Alex's approval or rejection of a specific Analysis Version and, for an approval, its selected Response Option.
_Avoid_: Action, ledger action

**Response Approver**:
The person authorized to make the final Decision after every required Prerequisite Approval has been satisfied.
_Avoid_: Sole approver, prerequisite approver

**Demo Persona**:
A fictional business actor with a stable identity across deployments, represented in each tenant by a purpose-built account binding.
_Avoid_: Tenant user, real person

**Alex Morgan**:
The fictional Material Planner and Response Approver identified across deployments as `RL-PERSONA-ALEX`.
_Avoid_: Authenticated operator

**Jordan Lee**:
The fictional Quality Approver identified across deployments as `RL-PERSONA-JORDAN`.
_Avoid_: Response Approver

**Taylor Brooks**:
The fictional Finance Approver identified across deployments as `RL-PERSONA-TAYLOR`.
_Avoid_: Response Approver, Quality Approver

**Prerequisite Approval**:
An independently authorized approval that a Response Option requires before the Response Approver may approve it.
_Avoid_: Evidence reference, attestation

**Finance Proposal**:
The exact Response Option, evaluated cost and Analysis Version submitted by Alex for Taylor's spending review. A changed response or analysis is a different proposal, not an extension of an earlier approval.
_Avoid_: Final Decision, selected response alone

**Submitted Response**:
Alex's formally submitted Response Option for a specific Analysis Version and evaluated cost, with a Finance Review when required. It is distinct from an option selected for comparison and still requires Alex's final Decision.
_Avoid_: Selected response alone, approved response, Finance approval

**Finance Review**:
Taylor's independent assessment of a Finance Proposal, recorded as pending, approved, rejected or superseded. Approval applies only to that proposal and does not replace Alex's final Decision; supersession preserves the earlier review history.
_Avoid_: Standing Authorization, automatic approval, Alex's approval

**Standing Authorization**:
A prior approval from an authorized persona that permits defined response types within stated limits, conditions, and an effective period.
_Avoid_: Blanket approval, app-role assignment

**Approval Satisfaction**:
The determination that a specific Response Option in a specific Analysis Version satisfies a valid Prerequisite Approval or Standing Authorization.
_Avoid_: Approval reference, role claim

**Execution Action**:
A bounded task or unsent draft created as a consequence of an approved Decision.
_Avoid_: Response Option, selected action

**Execution Attempt**:
One attempt to progress an Execution Action toward its predefined completion criterion, including its status and any failure information.
_Avoid_: Retry count, action version

**Current Decision**:
The approved Decision that governs future activity for a Disruption Case. A later approved Decision may supersede it without changing its historical record.
_Avoid_: Latest ledger action, active analysis

**Completed Execution Action**:
An Execution Action whose bounded internal artifact or simulated task reached its predefined completion criterion. It is not evidence that an external party or operational system acted.
_Avoid_: Externally executed, supplier completed

**Outcome Observation**:
A post-decision measurement linked to a Decision and, when applicable, an Execution Action.
_Avoid_: Outcome history, result

**Actual Observation**:
An Outcome Observation derived from a real business event or authoritative operational source.
_Avoid_: Live outcome

**Simulated Observation**:
An Outcome Observation generated for demonstration or testing rather than derived from a real business event. Its simulated status is permanent.
_Avoid_: Actual, live outcome

**Simulated Execution**:
A visibly labeled, deterministic progression of Execution Actions and Outcome Observations performed against the Demo Corpus.
_Avoid_: Live execution, external execution

**Demo Corpus**:
A collection of fictional business entities, communications, and operational records used to demonstrate Supply Response without personal, customer, or production data.
_Avoid_: Production data, anonymized customer data
