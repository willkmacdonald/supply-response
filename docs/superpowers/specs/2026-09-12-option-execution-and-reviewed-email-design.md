# Option-specific execution and reviewed supplier email

Status: approved by Will on September 13, 2026, under the
[email-to-mitigation journey](2026-09-12-email-to-mitigation-workflow-design.md).

## Action plans

Only a current approved Decision can produce an execution plan. Use the approved
option's actual quantities, costs and dates, not fixed combined-response values.

| Chosen response | Operational actions |
| --- | --- |
| Expedite Alpha partial shipment | Coordinate the approved partial shipment |
| Transfer from Dallas | Coordinate the approved Dallas-to-Chicago transfer |
| Resequence production | Coordinate the approved production resequencing |
| Combined response | Coordinate its approved partial shipment, transfer and resequencing |

All supported plans also include preparing the supplier communication and
updating disruption status. The communication reflects the selected response;
an internal transfer must not imply an Alpha shipment was ordered. Baseline and
blocked alternate-supplier options cannot generate executable plans.

For each action show plain-language purpose, owner, expected result, status and
what the app actually performs. Operational coordination remains a labeled
simulation unless a separately authorized real adapter exists. Do not reuse the
combined plan's fixed simulated observations for standalone options. Preserve
legacy plans and observations without rewriting history.

## Reviewed real email

The app prepares an editable fictional supplier email from the approved proposal.
Alex reviews subject and body in **Execute mitigation plan**. Display **From:
Alex**, the actual mailbox, and **To: Supplier Alpha (demo)—Will** with the actual
address. The only allowed recipient is the configured `will@willmacdonald.com`;
Alex sends from `agent@willmacdonald.com`. No CC/BCC, arbitrary recipients,
attachments, purchase-order changes or financial commitments in this increment.
Never derive the send destination from untrusted email text or a Reply-To field.

Use an explicit **Send email** action, separate from approval, saving a draft,
tab navigation and simulated playback. A changed draft requires a fresh review;
a changed/superseded approval blocks sending. Record the exact reviewed content
revision and actor. Supplier messages carry a visible fictional-demo disclaimer
and case reference. They may request recovery confirmation or describe the
approved demo response, but must not present the demo as a real purchase order.

Use a dedicated Microsoft Graph mail adapter under Alex's delegated identity;
Work IQ remains discovery/read, not the claimed sender. Microsoft documents
[draft creation](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0)
with `Mail.ReadWrite` and a separate
[send-draft operation](https://learn.microsoft.com/en-us/graph/api/message-send?view=graph-rest-1.0)
with `Mail.Send`, returning `202 Accepted` and saving to Sent Items. Required
tenant consent and delegated token setup must be verified separately. Do not
introduce tenant-wide application sending to avoid interactive authentication.

The web-reviewed draft is the content authority. After explicit Send, create the
provider draft from that frozen revision and submit it; do not send a long-lived
Outlook draft whose content could have changed outside the review. Persist the
provider draft identity before submission and verify content/recipient binding.
If external modification is detected, stop and require review. The capability
check must establish provider identity and reconciliation behavior before this
adapter is enabled; no undocumented atomic-send guarantee is assumed.

## Truthful status and retry safety

Keep durable draft, submitting, accepted, sent-confirmed, failed and uncertain
states. A server-side send claim prevents concurrent/repeated clicks from
creating duplicate sends. Persist correlation, reviewed revision and provider
identity. A timeout after submission becomes **Send status uncertain**; offer
**Check send status**, not an automatic resend. Do not claim exactly-once
delivery from a client idempotency key. Reconciliation must identify the exact
message, not just a matching subject, before allowing further action.

`202 Accepted` is not inbox-delivery evidence. Sent Items confirmation can be
shown as **Sent**, not **Delivered**. Acceptance for the demo includes Will
actually opening the received message. If reconciliation cannot determine what
happened, preserve the uncertain state and require human inspection; do not
silently create and send another copy.

Simulation never invokes the real mail adapter or changes an email to Sent.
Show simulated coordination progress separately from actual mail status. Running
simulation must not make the overall plan look complete while required supplier
communication remains unsent. Real email receipt is not proof of a real shipment,
inventory movement, production change or financial commitment.

## Acceptance

Test each feasible option's action set and values; infeasible options; independent
approval prerequisites; recipient/sender/role restrictions; draft edits; stale
approval; duplicate clicks; restarts; expired consent/session; explicit failures;
and ambiguous provider timeouts. Verify zero real sends during simulation.
With explicit live-send authorization, demonstrate Alex's reviewed email reaching
Will once and record its linkage to the exact approved proposal. Automated mocks
alone do not certify live delivery.
