# Planner spec conformance correction

Status: local implementation and independent code review complete through
`cb9aee5`. Actual SQL and native/live acceptance remain pending. This is not a
deployment record.

Approved design: [Evidence records and case dashboard](../superpowers/specs/2026-09-08-evidence-records-and-case-dashboard-design.md).
Correction plan: [Planner spec conformance](../superpowers/plans/2026-09-09-planner-spec-conformance.md).
Original audit: [Planner language audit](2026-09-09-planner-language-audit.md).
Correction base: `1217401` on `codex/planner-experience`.

## Card review checkpoint

Implementation `e49e4be` was independently reviewed and accepted against the
approved spec. Original delivery and the optional recovery shipment are explained
separately. Missing full-recovery dates are not described as supplier commitments.
Recommendation actions and predictions precede expandable ranking details.
Source statements, calculation inputs, validation conditions and navigation guards
remain unchanged.

The implementer recorded 229 passing frontend tests, a successful production build,
and two passing isolated browser tests at 1440×1000 and 390×844. The parent reviewer
inspected desktop and mobile screenshots, including expanded shipment and
qualification records. Work IQ and Microsoft Fabric pills appear below business
content, links and expanded details in those local renders.

The reported top-of-card pills did not reproduce locally. No speculative CSS fix
or browser-cache explanation was introduced. The user's locked live tab could not
be inspected; local screenshots do not constitute live acceptance.

Two initially raised review concerns were resolved through focused contract checks:

- `services/analysis/options.py` calculates the persisted service percentage over
  production orders. Customer-order-line wording requires exact one-to-one
  reconciliation in the presentation; the fallback does not invent a denominator.
- `integrations/workiq/message_evidence.py` validates configured source IDs and
  supplier sender or Quality author/team/channel before assigning source scopes.
  `mcp_evidence.py` also bounds discovery to those sources. The UI identifies
  Jordan Lee as the scenario contact, not separately verified message authorship.

## Lifecycle review checkpoint

Implementation `9354907` replaces raw API failures with allowlisted messages,
distinguishes standing authorization from a new approval, and presents the recorded
decision's response rather than the current mutable selection. Case, decision,
action and draft identifiers remain available in expandable details. Drafts stay
unsent and simulation states remain explicit.

Independent review found inherited-object-key handling in older shared role and
blocker display helpers. Correction `a9cde43` made role, blocker and comparator
lookups own-key-safe, with plain unknown labels and raw diagnostics in details.
The independent re-review accepted the lifecycle stage with no remaining findings.

The parent then freshly ran the full frontend suite (243 tests), production build,
and both isolated desktop/mobile presentation tests. All passed. The parent
inspected the regenerated desktop investigation row and mobile qualification card.
Non-blocking output consisted of the existing Vite bundle-size advisory and a
test-runner color-environment warning. No live acceptance is implied.

## Reporting checkpoint

Implementation `57dd57e` aligns Power BI headings, table labels and explanatory
paragraphs with the cards. The original delivery and proposed shipment have
separate narratives. The traditional walkthrough now has planner steps and
separate presenter notes preserving same-analysis, replay and shared-calculation
disclosures. Its comparison remains neutral before the AI-assisted route.

The disruption narrative no longer requires the disruption record's partial
quantity field, which it no longer displays. That field remains unchanged in the
source; it is not the separate optional shipment. Original quantity and exact
analysis/record scope are retained. No calculation, SQL, source-data, relationship,
page-ID or filter change was made.

The parent freshly verified `57dd57e`:

- 180 reporting tests passed: 54 generator, 86 Power BI project and 40 activation.
- Report-page, semantic-model and artifact-digest checks passed.
- Offline report-author validation: zero errors and zero warnings.
- `git diff --check` passed.

The tests include vendored Microsoft JSON schemas and Microsoft TOM metadata
parsing, not native report rendering or live DAX execution. The existing
Starlette/httpx deprecation warning is recorded, not suppressed. No frontend file
changed after the parent's 243-test/build/two-browser-test checkpoint.

Task 3 review required one correction: overview shipment/transfer answers omitted
per-unit cost despite the detail pages having it. Parent review additionally found
two report labels calling the stored service percentage an order-line measure.
The backend denominator is production orders; unlike the conditional frontend
wording, those report measures have no one-to-one customer-line reconciliation.
Correction `38b1ca2` adds single-record-scoped additional cost per component unit,
preserving zero versus missing values, and names the percentage's production-order
basis. Independent re-review approved it with no remaining findings. Parent fresh
verification at that commit passed 182 tests (56 generator, 86 project, 40
activation), all three generator/digest checks and offline report validation with
zero errors/warnings. The nine core analysis/scenario-contract tests also passed.

## Final-review web correction

`fa2488a` adds a direct do-nothing → recommended-response comparison using the
existing predictions. It preserves exact money values, distinguishes missing or
ambiguous baselines, and makes no benefit claim when the displayed values match.
Component identity and the validated customer-line/production-order interpretation
remain explicit. It also explains the existing coordination score's weights and
states that the score is not a probability of failure.

Parent fresh verification passed 246 frontend tests, the production build and two
isolated browser tests. Desktop and mobile recommendation-card screenshots were
personally inspected; values are readable, comparison precedes ranking details,
and the footer remains last. Independent re-review approved the correction with
no remaining web findings.

## Final-review reporting correction

`cb9aee5` adds readable option, action, status and outcome
labels to the existing read-only report queries. Original fields and encoded
identity keys remain unchanged. Raw codes are inspectable in Source details;
display aliases carry grouping metadata so matching names do not erase identity.
Scalar summaries use guarded extraction rather than assuming a display name is
unique. A small outcome Source-details table sits below the shortened chart;
native readability remains a release check.

Following [Microsoft's DirectQuery guidance](https://learn.microsoft.com/en-us/power-bi/guidance/directquery-model-guidance), these are report-query projections,
not new database objects or changes to synthetic records. The exact metadata
syntax was obtained from the locked Microsoft TOM serializer, then parsed and
checked for the intended grouping references. Parent fresh checks passed all 186
reporting tests, three generation/digest checks and offline author validation
(zero errors/warnings). Actual SQL/DAX execution is not established by those tests.
The parent repeated the full 186-test suite and all three drift checks against the
committed correction; all passed. Independent final re-review approved this change
and the previously reviewed web correction with no remaining code findings. It
explicitly did not grant deployment or native/runtime acceptance.

## Audit coverage

| Original audit finding | Correction and retained meaning |
| --- | --- |
| 1. Disruption versus optional recovery | Original delivery and proposed shipment separated in app and report; no source or baseline-supply rewrite. |
| 2. Storage language in the narrative | Delivery, stock, shipment and analysis lead; snapshot/replay disclosures remain in their proper context. |
| 3. Ambiguous missing values | Full-recovery absence says no date recorded; retrieval failure is separate; generic missing values do not invent a cause. |
| 4. Algorithm before business effect | Recommended actions and a direct comparison with doing nothing precede expandable comparison rules; missing/tied results are explicit. |
| 5. Assumptions mislabeled | Mixed content is labeled assumptions and unresolved questions; combined response identifies its actions. |
| 6. Technical source caveats | Proposal, approval, completion and qualification review remain distinct; original excerpts and attribution limits preserved. |
| 7. Retrieval transparency | Actual analysis-bound retrieval/check results retained; configuration does not claim successful live activity; bottom platform pills verified in local desktop/mobile renders. |
| 8. Approval language | Authorization and recorded decision are distinct; roles readable; unknown codes and IDs relegated to details. |
| 9. Raw API errors | Allowlisted plain errors; no raw response bodies or invented recovery instructions. |
| 10. Execution/outcome language | Explicit unsent drafts, known action names, simulated results and sequential steps; coordination score explained, controls unchanged. |
| 11. Matching Power BI language | Business labels and display values, costs and accurate service-metric basis; raw details and identity/filter contracts retained. Actual SQL/native validation remains pending. |
| 12. Navigation/walkthrough | Exact approved route names; planner steps separate from presenter disclosures; neutral traditional comparison. |

## Remaining checkpoints

- The first full correction-range review found two Important gaps:
  the recommendation lacked a direct business comparison with doing nothing,
  and Power BI headings were friendly while some underlying displayed values
  remained technical. It also requested a plain explanation of execution risk.
  Both gaps and the score explanation were corrected and independently re-reviewed
  in `fa2488a` and `cb9aee5`; no code-review findings remain open.
- Live-tab/native Power BI acceptance and deployment remain separate.
- Execution of the changed SQL display queries on the dedicated synthetic test
  VM is blocked pending the user's specific source-transfer authorization. The
  safety reviewer rejected the attempted transfer before execution; no changed
  files were uploaded and no new SQL test run occurred. All 138 local SQL cases
  skipped without an engine; this is not evidence of runtime correctness.
- Native reporting acceptance must check that the generated visual queries retain
  distinct option/action identities when friendly labels match, and that each
  card opens its exact analysis-bound supporting record. A metadata-parser pass
  or synthetic SQL test cannot establish those rendered navigation behaviors.
- The locked Mac prevented live-tab inspection. Two read-only public HTML
  requests also timed out; that does not establish that the app is down or explain
  the reported pill placement. No browser-cache explanation is claimed.

No correction in this record has been pushed, merged, deployed or published.
Report-link activation remains gated on its separate acceptance requirements.
