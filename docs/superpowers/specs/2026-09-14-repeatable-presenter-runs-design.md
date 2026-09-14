# Repeatable presenter runs

Status: approved by Will on September 14, 2026.

## Intent

Each presentation must begin as a genuinely fresh response journey even when
the presenter reuses the same marked supplier email. A prior Taylor approval,
Alex decision, execution plan, or outcome must never appear in the new run.
Retained runs remain immutable; freshness comes from creating a new Case
Instance, not from clearing or rewriting an old one.

This design amends the cross-run deduplication rule in
`2026-09-12-presenter-controlled-inbound-disruption-design.md`. Stable Outlook
message identity remains part of the source binding, but it is no longer the
complete Case identity for presenter runs.

## Root cause being corrected

The current inbound-case identifier hashes Alex's tenant, mailbox, and the
email's stable Internet Message-ID. Rechecking the same email therefore reopens
the same Case Instance. Because Finance reviews and final Decisions are durable
records bound to that case and analysis, Taylor's prior approval and Alex's
prior decision correctly reappear. The approval is not global, but the current
entry behavior makes it appear permanent across demonstrations.

The header action **Open case dashboard** came from the earlier exact-case
Power BI design. It is now redundant with the deliberate comparison route
**Explore in Power BI** and is outside the approved presenter sequence.

## Presenter flow

1. Opening the application without case parameters shows no active case or
   approval state.
2. Alex clicks **Check email for disruptions**. The server performs the bounded
   Work IQ mailbox check and creates a new opaque presenter-run identifier for
   that check result.
3. The page shows the matching supplier email for review. The check itself does
   not create a case, analyze data, request approval, or send email.
4. Alex clicks **Analyze this disruption**. The application revalidates the
   email and creates a new Case Instance whose identity includes both the stable
   email identity and the presenter-run identifier.
5. Repeated clicks, concurrent requests, or a response retry within that same
   presenter run return the same case. A later mailbox check receives a new run
   identifier and therefore creates a different case, even if it uses the same
   email.
6. The new case starts with no Analysis Version, proposal selection, Finance
   review, Approval Satisfaction, Decision, execution action, draft, playback,
   or outcome. Normal analysis then begins from the source-bound case.
7. When the selected response requires Finance review, tab 4 starts by waiting
   for a new Taylor decision for this run. Only that run's Taylor approval can
   enable Alex's final approval.

Taylor and Alex decisions remain permanent and auditable within their retained
run. The application never resets an existing approval or reassigns it to a new
case.

## Run identity and API contract

`POST /api/inbox/check` returns a server-created run identifier with the inbox
result. It is an opaque value with a strict format and is not derived solely
from the email. `POST /api/inbox/cases` requires that run identifier alongside
the Internet Message-ID and review fingerprint.

The inbound Case identifier is deterministic over tenant, Alex mailbox, stable
email identity, and presenter-run identifier. The Case payload retains the run
identifier for lineage and retention decisions. Historical cases without a run
identifier remain readable and are never silently rebound to a new run.

The existing sender, recipient, subject/body marker, source-content,
operational-data, actor, and runtime checks remain unchanged. A run identifier
does not authorize a case by itself. Work IQ must still re-read the exact email
and all source validation must pass.

## History retention

The live demo retains the current presenter run and the three most recent prior
presenter runs. Older presenter runs are permanently removed. A presenter run
is a live showcase case with a bound supplier email; this includes older inbound
cases created before explicit run identifiers were introduced.

Retention is enforced server-side when a new presenter case is created. The new
case and pruning decision occur in one transaction so a failure cannot leave a
partially deleted history or a partially created run. Ordering uses the durable
case-recorded timestamp with Case ID as a deterministic tie-breaker.

Pruning removes the complete aggregate for each expired case: analysis claims,
evidence, Finance review revisions, proposal selections, approval
satisfactions, Decisions, outbox events, execution projections/actions,
drafts, attempts, execution events, playbacks, observations, case projection,
operational snapshot, and Case Instance. No dependent or reporting row may be
orphaned.

Automated-test cases, fallback cases, showcase cases without a supplier-email
binding, operational source data, and the traditional reporting dataset are
outside the retention set and remain untouched. Retention never rewrites the
three prior runs that remain.

The first deployment includes one bounded cleanup using the same retention
operation, leaving the newest presenter case plus its three most recent
predecessors. The deletion scope and counts must be previewed before that cleanup
is applied and verified afterward.

## Power BI entry points

Remove **Open case dashboard** from the case header in all modes. Preserve:

- **Explore in Power BI** as the broad, traditional rows/charts investigation;
- exact card-level supporting-data links for evidence used in the current
  analysis; and
- Power BI availability messaging where the comparison or card links need it.

The removal changes navigation only. It does not alter published reports,
report filters, saved evidence, or reporting data.

## Failure behavior

- A failed mailbox check creates no run or case visible to the presenter.
- An unsupported, changed, or conflicting email creates no case.
- A failed case-creation/pruning transaction leaves both the retained history
  and case count unchanged and shows an actionable retry message.
- A failed analysis keeps the new source-bound case available for retry without
  borrowing any state from another run.
- Reopening a retained historical run continues to show that run's own approval
  and decision honestly.

## Acceptance

Automated coverage must prove:

1. Two successful inbox checks mint different presenter-run identifiers.
2. The same validated email analyzed under two different run identifiers creates
   two different cases.
3. Repeated and concurrent creation within one run returns one case.
4. A new run cannot expose the earlier case's analysis, Finance review, Taylor
   approval, Alex decision, execution records, or outcomes.
5. Creating a fifth retained presenter run leaves exactly the current run and
   three prior runs, deletes every dependent row for the expired case, and
   leaves excluded case/data categories unchanged.
6. A forced pruning failure rolls back both creation and deletion.
7. The case-header **Open case dashboard** link is absent while **Explore in
   Power BI** and exact supporting-data links remain.

Live acceptance must start from the bare application URL, reuse the same marked
supplier email for two consecutive runs, and show distinct Case IDs. In the
second run, tab 4 must require a new Taylor review even after the first run was
approved by Taylor and Alex. The retained-run list and database counts must
show no more than the current run plus three historical presenter runs. No
approval, final decision, execution, or email send is performed merely to test
the mailbox check.

## Self-review

The design contains no placeholders. It distinguishes a fresh run from email
deduplication, preserves within-run idempotency and immutable retained history,
defines the exact retention boundary, excludes unrelated data, and makes the
Power BI navigation change explicit. The transaction and live-acceptance rules
prevent partial cleanup or a false claim that client-side state clearing created
a fresh business run.
