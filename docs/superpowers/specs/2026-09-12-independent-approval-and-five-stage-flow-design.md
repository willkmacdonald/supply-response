# Independent approval and five-stage flow

Status: proposed written design under the
[email-to-mitigation journey](2026-09-12-email-to-mitigation-workflow-design.md).

## Presentation

Use five tabs within the existing investigation section: **Understand the
disruption**, **Investigate responses**, **Choose a response**, **Review and
approve**, **Execute mitigation plan**. Keep full-width cards stacked vertically.
The third tab contains option comparison and the existing explanation overlay;
move approval and execution into their dedicated tabs without duplicating forms.
Tab clicks are navigation only, never mutations. Preserve selected-option and
form state across tab changes. All tabs are inspectable; unavailable actions
explain their prerequisites rather than presenting an unexplained gray box.

The explanation describes deterministic ranking and constraints, distinguishing
AI-written explanation from calculation, recommendation and human authorization.
Selecting an option shows **Selected response** immediately. The approval tab
shows its cost, impacts, required reviewers and next available action.

## Approval behavior

Reuse Taylor's existing Finance Approver identity and Alex's existing planner /
response-approver identity. Server-side tenant/object/role binding determines
authority; a query parameter, display name or local persona selector does not.
Taylor receives an authenticated review list and exact-request deep link. Alex
sees Finance status without impersonating Taylor. No new notification channel is
required for the first increment; the presenter can open Taylor's review link.

For new workflow-version cases, costs strictly greater than $20,000 require an
explicit Taylor review. Existing canonical expedite ($22,500) and combined
($24,750) options therefore require Finance. Transfer ($2,250) and resequence
($0) do not; explain **Finance review not required—within the spending threshold**.
Use actual evaluated option cost, not these example amounts as branching rules.
The old $25,000 standing authorization must not satisfy these new requests.

Each submitted proposal binds case, analysis, option, cost, relevant evidence and
constraints to an immutable revision. States are pending, approved, rejected or
superseded. Taylor can approve or reject; rejection requires a reason. Record
authenticated actor, server time and exact proposal revision durably. A rejection
does not change company policy or turn text such as “budget $10,000” into a new
automatically enforced threshold.

After rejection, Alex can revise the selection and submit a new proposal. Never
overwrite the rejected record or reuse its approval. New analysis or a changed
proposal invalidates prior approval for final-decision purposes. Resubmitting an
unchanged rejected proposal creates a new explicitly submitted request, not a
silent reset. Concurrent submissions and repeated commands are idempotent.

Alex's final approval remains a separate action after all prerequisites are
satisfied. Server checks the current proposal and Finance outcome atomically;
stale clients cannot approve superseded or rejected proposals. Taylor cannot
finalize Alex's Decision or send mail. Selecting an infeasible option, including
unqualified Supplier Beta, cannot bypass planning constraints. Baseline remains
comparison only. Existing historical Decisions and standing-authorization
evidence remain readable and immutable under their original workflow version.

## Verification boundary

Prove positive and negative API authorization, exact-threshold behavior, rejection
and resubmission, stale-analysis races, durable audit, repeated-click safety and
cross-session status updates. In the real app, separately sign in as Taylor and
Alex; capture rejection and successful approval journeys. Merely provisioning
Taylor or showing a Finance badge is not acceptance evidence. Test keyboard tab
navigation, selection feedback and readable waiting/error states as well.
