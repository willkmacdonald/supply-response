# Planner-language review

Date: 2026-09-09
Reviewed revision: `1217401` (planner-experience branch)
Scope: application cards, supporting records, status/error/decision/action states,
Power BI page definitions and display measures, and the traditional walkthrough.

This is a source-based review, not a new native-browser visual acceptance test.
No application code, source messages, data, permissions, or deployments were changed.

## Verdict

The three-row investigation structure is sound, but the language requirement is
not consistently satisfied. The interface often describes data storage and
validation instead of answering the planner's business question. This is broader
than replacing “saved disruption.” Some wording also blurs business distinctions.

Retain the approved sequence and left-hand labels. Each card should read:
business question → direct answer → quantities/dates/costs and unresolved conditions
→ clearly named supporting links → compact source/check/time footer.

Do not remove meaningful uncertainty or imply that a proposal is approved,
that a prediction has happened, or that an earlier retrieval is continuous monitoring.

## Findings requiring correction

### 1. Original disruption versus optional recovery is unclear — highest priority

The disruption card says “Recorded partial supply: 0 units; date: Unavailable,”
while the response card shows a 3,000-unit receipt. Power BI's Disruption Answer
also calls the zero “in the partial response.”

The canonical data deliberately contains both: disruption partial quantity zero,
and a separate optional 3,000-unit expedited receipt dated September 6. The
no-mitigation calculation excludes that optional receipt. This is not evidence
that a missing value was converted to zero. It is a failure to explain which
business situation the number describes.

Lead the first card with the missed original delivery. Present the optional
expedite on the recovery card, explicitly as a response under consideration.
Do not overwrite the disruption's zero with 3,000 or count an optional shipment
as baseline supply. Do not describe zero as an observed delivery outcome.

Sources: `apps/web/src/components/InvestigationEvidence.tsx:168`,
`fabric/report_model.py:1072`, `data/synthetic/rl001.py:147`,
`tests/domain/test_rl001_contract.py:46`, `tests/analysis/test_rl001_options.py:42`.

### 2. Storage terminology occupies the business narrative

Examples include “Saved disruption,” “saved partial shipment,” “remaining
recovery date in the saved plan,” and “saved planning analysis.” Inventory adds
a main-body sentence about a separate retrieval timestamp being unavailable.

Use delivery, shipment, stock, plan, and analysis where those words actually help.
Put the fact that information was captured earlier in the footer once. Keep a
prominent historical-analysis notice when the user is viewing an older version.
“Saved” is appropriate for an explicit save/history operation, not a shipment label.

Sources: `InvestigationEvidence.tsx:168,253,276,385,389`;
`apps/web/src/components/InvestigationFlow.tsx:21`.

### 3. “Unavailable” hides different meanings

One formatting helper renders absent or invalid dates as “Unavailable.” Missing
records and absent business commitments also use similar wording. A planner
cannot tell whether the supplier has not committed, the source omitted a value,
or the application could not retrieve/validate it.

Use “No date confirmed” only when supported by the source; “No date recorded”
when a field is absent; and “We couldn't retrieve the shipment details” only
for a retrieval failure. If the cause is unknown, say “Shipment details aren't
available for this analysis.” Preserve zero as zero when it is a valid fact.
This requires context-aware messages, not a global string replacement.

Sources: `apps/web/src/components/plannerFormatting.ts:5`,
`apps/web/src/components/SupportingRecordDetails.tsx:6`, `fabric/report_model.py:357`.

### 4. The recommendation explains the algorithm before the business benefit

The main recommendation lists retained comparison stages and threshold values.
“This option stayed in consideration…” is technically descriptive but makes
the planner reconstruct why the recommendation matters.

Lead with the recommended actions and their supported effects compared with
doing nothing: additional supply, remaining shortage, customer-service impact,
and additional cost. Retain exact ranking rules/tie-breaks under “How the options
were compared.” Do not invent a business advantage when the final tie-break
was an identifier rather than a material difference.

Sources: `apps/web/src/components/ExposurePanel.tsx:19`,
`apps/web/src/components/plannerFormatting.ts:39`.

### 5. Assumptions are mislabeled as uncertainty

“What remains uncertain” displays every option assumption, including statements
such as “Alpha receipt is confirmed for its offered due date.” That heading
misclassifies the content.

Separate calculation assumptions from unresolved supplier commitments. Until
the data supports that separation, use “Assumptions and unresolved questions.”
“Combined response” should also explain its constituent actions, using the
actual option definition rather than forcing the user to infer them.

Sources: `apps/web/src/components/ExposurePanel.tsx:22`,
`apps/web/src/components/optionLabels.ts:6`, `services/analysis/options.py:324`.

### 6. Source caveats are written for implementers

Examples: “separate source roles; a receipt is not an approval” and “Author
identity is not a separate verified field in this saved payload.”

Explain the business distinction: a proposed shipment is not an approved action;
the qualification review date is not permission to use the supplier. Keep source
attribution limits in Source details unless they undermine the displayed claim.
Do not falsely present the scenario's named Quality Manager as verified authorship.

Source: `InvestigationEvidence.tsx:383,465`.

### 7. Retrieval transparency is useful but still too technical

The platform footer placement and actual retrieval timestamps should stay.
However, “Evidence policy checks passed,” “Evidence authority check failed,”
“Synthetic fixture,” and “Not accepted as authoritative evidence” remain cryptic.

Use a short visible summary such as “Retrieved for this analysis at [time]” and
“Required checks passed,” with an explanation of the actual checks in details.
For failures, explain the consequence: “This source can't be used to approve
the response,” when that is the actual consequence. Context-only sources must
remain distinguishable from evidence supporting approval. Never translate a
successful check into “Delivery confirmed” or a numerical confidence claim.

The header's “Live mode” reflects configuration, not proof of a successful live
retrieval. Label it accordingly and use actual results for per-source success.

Sources: `apps/web/src/components/evidenceStatus.ts`,
`apps/web/src/components/EvidenceFooter.tsx`, `apps/web/src/components/CaseHeader.tsx:60`.

### 8. Decision language is hard to act on

“Recorded authorization satisfied,” “No satisfied authorization recorded,”
“Required roles,” and raw IDs in the approved receipt obscure who still needs
to approve what. Unknown blocker codes can also surface as technical strings.

Show the response name, approval status, and outstanding role-specific requirements.
Use “Approval recorded” only if the recorded satisfaction actually represents
approval; otherwise name the authorization requirement accurately. Keep IDs and
runtime values in decision details. Preserve the distinction between selecting,
approving, generating a draft, and executing an action.

Sources: `apps/web/src/components/DecisionPanel.tsx:29,43`,
`apps/web/src/components/plannerFormatting.ts:24`.

### 9. Errors still expose the raw API response

The API constructs `API request failed: [status] [JSON]`; the workspace hook
includes it in the visible error. This can reproduce the confusing 503 experience.

Give a plain-language failure, its known consequence, and a supported next step.
Keep safe diagnostic codes in expandable details. Do not claim which source failed
or suggest retrying, recreating a case, or switching to sample data unless that
action is actually supported for the specific state.

Sources: `apps/web/src/api.ts:25`, `apps/web/src/hooks/useCaseWorkspace.ts:140`.

### 10. Execution and outcome labels need the same treatment

“Draft Artifact,” “Simulated playback,” mechanically expanded action/metric
names, and “Outcome observations” are not planner-oriented. Step labels 05 and
06 also follow the new three-row structure without explaining the gap.

Name the actual action or document, show whether it is only drafted, and keep
simulation explicit. Prefer “Simulated results” to “playback observations.”
Do not label all draft types as email without checking their type. Explain the
execution-risk score as a comparison measure, not a probability of failure.

Sources: `apps/web/src/components/ExecutionPanel.tsx:15,27,37`,
`apps/web/src/components/OutcomePanel.tsx:15,20,25`,
`apps/web/src/components/OptionComparison.tsx:30`, `services/analysis/options.py:30`.

### 11. Power BI needs matching language, not just matching data

Tables generate most column labels by capitalizing internal field names, yielding
“Executable,” “Is baseline,” and “Uncovered part demand.” Other visible wording
includes “Supporting saved records,” “Current governing decision,” “Projection
updated,” and “Review the decision boundary.”

Use explicit business display labels and friendly value mappings. Keep technical
keys in Source details. Match terminology between app and report (including
current/original supplier, component units, additional cost, and order lines).
Keep revenue versus total order value, customer orders versus order lines, and
prediction versus actual outcome distinctions intact.

Sources: `fabric/report_pages.py:25,89,530,713,755`,
`fabric/report_model.py:852,933,1255`.

### 12. Navigation and walkthrough overemphasize implementation

“Replay of saved evidence; this is not a new discovery run” appears as a general
navigation explanation. The walkthrough mixes presenter instructions with long
warnings about calculation engines and decision lineage.

Lead with “Investigate in Power BI” versus “Review the assisted recommendation,”
and explain once that both use the same information from this analysis. Keep
replay versus fresh retrieval explicit in a compact note. Organize the walkthrough
around what the planner checks, learns, and decides; retain technical limitations
in presenter notes. Never claim independent Power BI recalculation or measured
time savings that this demonstration has not established.

Sources: `apps/web/src/components/PlanningRoutes.tsx:24`,
`docs/demo/traditional-and-assisted-walkthrough.md`.

## Proposed business narrative for the existing nine cards

These are copy targets, not new runtime facts. Quantities, dates, business states,
costs and remaining balances must be derived from the matching supported records.

| Card | What the primary content should answer |
| --- | --- |
| What changed? | Which supplier cannot meet the original delivery, for which component, quantity, plant and date? |
| What do we have available? | How much can Chicago use now, after quality holds and stock reserved for other requirements? |
| What does that put at risk? | Without a response, which supported service metrics and production/customer commitments are exposed? |
| What can the current supplier still supply? | What is offered or planned as an option, when could it arrive, what is the additional cost, and what remains unconfirmed? |
| Can another plant help? | How many units could Dallas transfer to Chicago, by when, and at what additional cost? |
| Can we use the alternate supplier? | Is Supplier Beta qualified, and if not, which requirements remain outstanding? |
| Compare the options | How do the alternatives compare with doing nothing on shortage, service, cost and requirements? |
| Recommended response—and why | Which actions are recommended, what improvement is expected, and what risk remains? |
| Review and approve | What is selected, what approvals/requirements remain, and what action would the button authorize? |

## Recommended implementation order

1. Correct business meaning first: original delivery versus optional recovery,
   missing versus unconfirmed, assumptions versus uncertainties, and action states.
2. Apply a consistent copy pass to the app and Power BI display definitions;
   preserve original source excerpts and immutable historical analysis data.
3. Simplify status, errors, navigation and the walkthrough without weakening
   evidence, approval or simulation boundaries.
4. Verify populated, missing, conflicting, historical, fallback and failed states,
   then native text fit and exact card-to-report consistency. A successful happy-path
   screenshot alone is not sufficient acceptance.

No implementation or publication was performed as part of this review.
