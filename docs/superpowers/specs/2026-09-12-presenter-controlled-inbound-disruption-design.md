# Presenter-controlled inbound disruption

Status: proposed written design under the
[email-to-mitigation journey](2026-09-12-email-to-mitigation-workflow-design.md).

## Scope and source identity

Will's mailbox (`will@willmacdonald.com`) plays Supplier Alpha and sends a
fictional disruption to Alex (`agent@willmacdonald.com`). Keep **Supplier Alpha
— Current supplier** as the business label; disclose the actual sender address
and demo role in source details. Do not change Microsoft directory display names
or pretend the previous seeded message came from Will.

Use the current Work IQ discovery → message retrieval → validated evidence path.
New messages need case-specific source bindings; the old fixed seeded message ID
cannot be required for discovery or silently substituted after a lookup fails.
Do not introduce direct Graph discovery as an unlabeled fallback. Work IQ errors
must remain visible, with no manufactured message content or citation.

The first increment remains the bounded fictional RL-001 scenario, not general
mail ingestion. Require the configured supplier sender, recipient mailbox and a
demo marker plus supported order/component references. Proposed subject format:
**[Supply Response Demo] RL-001 | Supplier Alpha | unique run reference**.
Validate the actual sender metadata, not a quoted address in the body. Treat
email text as source data, never app instructions, authorization or an arbitrary
URL to fetch. Sanitized excerpts must not execute HTML/scripts.

## Presenter interaction

**Check for supplier disruptions** performs a bounded, on-demand discovery. It
does not run on a timer, create cases, approve plans or send mail. Show checking,
new candidates, no new matching messages, partial search and actionable failure
states distinctly. Multiple matches produce a reviewable list, not an arbitrary
first-message choice. Handle pagination within an explicit bound and disclose
incomplete results instead of reporting an exhaustive empty result.

A newly discovered message received within the preceding five minutes uses an
Outlook icon and **Inbound email from Supplier Alpha just received**. Older
messages say **Inbound email from Supplier Alpha found**. Display actual subject,
sender and received time, separately from the fictional scenario date and service
retrieval time. Reopening an already processed message must not announce it as
new. Five minutes is a proposed presentation rule, not a mailbox guarantee.

Offer **Open supplier email** and **Review disruption**. The review shows the
actual excerpt and identified disruption facts. Explicit **Create case from this
email** confirms case creation. Extract supported supplier statements from this
message; do not use a new email merely to trigger the old seed facts. Missing or
conflicting essential facts block case creation with an explanation. Fabric
remains the authority for operational inventory/order/cost records; conflicting
supplier assertions cannot overwrite it. Unsupported scenarios remain visible
but cannot become apparently validated RL-001 cases.

## Persistence and card fidelity

Persist tenant/mailbox/source identity and validated message metadata/content
with the case's evidence binding. Deduplicate case creation server-side using a
stable mailbox message identity and an atomic unique claim. Concurrent clicks
return the existing case rather than creating duplicates. Subject, body hash and
received time alone are not adequate identity. Verify Work IQ's usable stable
identity behavior for moved messages before enabling this path; do not assume
the old URL or a mutable folder ID is a durable key.

The **What changed?** card keeps the current visual structure, original supplier
excerpt, bottom Work IQ footer and Outlook link. Every field and link must match
the message bound to that case. Old cases retain their original source identity;
they are not migrated by globally replacing the supplier address or message ID.
Reopening a case does not refresh evidence or silently bind a newer email.

## Acceptance

Use a newly sent marked message from Will to Alex, not the seed. Prove Work IQ
discovery, content retrieval, sender validation, correct citation and case
creation. Verify multiple matches, older messages, no results, malformed input,
untrusted instructions, incomplete search, duplicate/concurrent checks, reopening
and source movement behavior. Confirm the new card opens the actual new email
in Alex's Outlook account and historical citations remain unchanged.
