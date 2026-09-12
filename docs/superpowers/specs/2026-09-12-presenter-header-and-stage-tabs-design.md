# Presenter header and stage tabs

## Purpose and approval

Will presents this demonstration himself. It is not a visitor-facing tutorial or
marketing page. The opening should establish the story; the investigation should
let him reveal one stage at a time without tall, tightly wrapped columns.

The conversational design and this written specification were approved by the
user September 12, 2026. Implementation proceeds with Codex review between tasks;
the user will revisit the design after seeing the built product.

This is a focused amendment to
`2026-09-08-evidence-records-and-case-dashboard-design.md`: it supersedes the
three-row, left-to-right card layout and the existing header wording only.
Existing evidence fidelity, approval gates, exact record links, planner language,
and bottom-of-card source transparency requirements remain in force.

## Opening box

Keep the eyebrow: **RL-001 · Supply Disruption Response**.

Replace **Progressive Case workspace** with:

**Respond to supply disruptions with AI**

Supporting paragraph:

AI brings together supplier messages, inventory, and customer orders to assess
the impact of a delay, compare recovery options, and support the planner's decision.

Replace the prominent mode badge with a quieter line at the bottom of the box:

- Configured live mode: **Fictional scenario · Uses live Microsoft services**.
- Fallback mode: **Fictional scenario · Uses predefined sample data**.
- Runtime not established: **Fictional scenario · Service mode not yet available**.

The mode line explains configuration, not a successful retrieval or continuous
service-health guarantee. Keep actual errors and retrieval results separately
visible. Retain case controls, case details, scenario time, and existing report
actions; do not change their behavior or add a new mode switch.

## Three tabs within the investigation section

Only the existing nine-card investigation changes to tabs. The header, case
selection, activity display, and surrounding page do not become separate tabs.

| Tab | Cards, top to bottom |
| --- | --- |
| **1. Understand the disruption** | What changed? → What do we have available? → What does that put at risk? |
| **2. Investigate responses** | What can Supplier Alpha still supply? → Can another plant help? → Can we use the alternate supplier? |
| **3. Make the decision** | Compare the options → Recommended response—and why → Review and approve |

Use the existing card components and business logic. The table defines order,
not replacement source facts. Keep supplier roles explicit inside each card.

The first tab is initially selected. All three remain freely selectable; no
wizard gate, automatic stage advancement, or new Next/Back buttons are needed.
Each panel contains a single vertical stack of full-width, content-height cards.
Remove narrow three-column constraints, equal-height stretching, and excessive
space distribution. Text and metrics should wrap naturally without becoming
unbroken page-wide paragraphs. Keep normal page scrolling, not nested scrolling.

Tab selection is presentation state. Switching tabs must not fetch sources,
create an analysis, change the case/analysis URL, reset the selected option or
decision form, submit an approval, or replay an operation. Preserve mounted card
state while hiding inactive panels and excluding their controls from focus and
the accessibility tree. A different case starts at the first tab; ordinary
rerenders and same-case operation completion do not unexpectedly change tabs.
Reload persistence for tab selection is not required.

Keep analysis-level provenance, activity/errors, and required-source warnings
outside the hidden panels so they remain visible regardless of selected stage.
Existing card-specific warnings stay beside the affected claim, and approval
blockers remain enforced regardless of which tabs have been viewed.

## Source actions, details, and footers

Keep the notes and platform/retrieval/validation footers at the bottom of each
card. Do not promote platform branding above the business question. Do not
replace actual retrieval timestamps with animated or inferred live indicators.

Use a consistent lower-card source area: source identity, optional original
excerpt disclosure, **Source details** disclosure, clearly labeled source action,
then the existing compact footer. Where a card has multiple sources, identify
each separately; do not merge their claims or destinations. Derived cards keep
their existing calculation/supporting-record explanations; do not fabricate a
source-detail disclosure or external message link just for visual uniformity.
When an expected source or link is unavailable, state that clearly.

Add a small recognizable Outlook product icon beside **Open supplier email**
and a Teams product icon beside **Open Quality Teams post**. Keep the text,
link behavior, and trusted-destination validation. Icons identify the destination
application, not the discovery/retrieval mechanism; Work IQ attribution stays
in its evidence footer. Do not attach product icons based on arbitrary source
text or render a clickable icon for an untrusted/missing URL.

Use local reusable vector assets from a verified Microsoft asset source, record
their origin and applicable usage terms, and avoid remote icon requests. No
AI-generated imitations or icon-only links. Icons are decorative to screen
readers because the adjacent link text provides the accessible name. Other
source actions retain accurate text; this scope does not require more logos.

## Implementation boundaries

### USD display amendment — September 12, 2026 (corrected scope)

Display all structured financial totals in USD with a dollar sign, thousands
separators, and no cents, rounded to the nearest dollar (50 cents rounds up).
This includes revenue at risk, margin at risk, response cost, full and compact
option metrics, both sides of response comparisons, and monetary predicted and
observed outcomes. The prior revenue-only scope was incomplete.
Supplier and plant-transfer per-component prices, supporting-record prices, and
customer unit revenue retain two decimal places (for example, $7.50 per unit).
Monetary comparison thresholds use USD but preserve exact policy precision.
This is display formatting, not currency conversion: preserve exact stored
amounts, calculations, comparison decisions, and original source-message excerpts.

Expected components: CaseHeader for copy/layout, InvestigationFlow for local tab
state and panels, EvidenceSource for labeled icons, and scoped styles/tests.
Any shared icon component should remain small. Audit existing source-detail
placements and change only the components needed for consistent treatment.

No backend, schema, synthetic-data, calculations, source URL, reporting view,
Microsoft permissions, authentication, or approval behavior changes. Do not
change Power BI to match the tab layout. Deployment remains a separately
verified release step; local screenshots are not evidence of a deployed change.

## Acceptance checks

1. Header uses the approved title/paragraph and truthful, subordinate mode line
   in live, fallback, and unavailable-runtime states.
2. Exactly three labeled tabs appear within the investigation; only the active
   panel is visible. Every stage retains its original three cards in order.
3. Keyboard users can navigate tabs with arrows/Home/End and activate with
   Enter/Space; roles, selected state, panel associations, focus indicators,
   and hidden-panel exclusion follow accessible tab behavior.
4. Switching away and back preserves option selection and decision inputs,
   makes no new network requests, and does not submit or replay any action.
5. Source links retain exact validated destinations, text labels, and safe
   new-tab behavior. Outlook/Teams icons appear only on matching trusted links.
6. Missing evidence, source failures, fallback provenance, approval blockers,
   actual retrieval times, and footers remain truthful and readable.
7. Desktop and 390px mobile browser proof covers all three panels: one-column
   cards, no clipped labels or page-wide overflow, no stretched empty cards,
   visible notes, and usable source actions. Tabs may wrap their labels on
   mobile but must remain distinguishable and keyboard accessible.
8. Run relevant regression tests, all frontend tests, and a production build;
   inspect screenshots and independently review before release.

## Design self-review

Checked against the earlier spec: source attribution, record correlation,
fictional/live distinction, footer placement, and explicit approval remain
unchanged. The only superseded spatial requirement is the three-row/three-column
arrangement. No placeholders or unresolved product choices remain. Asset origin
verification and visual testing are concrete implementation checks, not permission
to silently substitute unrelated icons or invent retrieval claims.
