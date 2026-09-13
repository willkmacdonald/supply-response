# Email-to-mitigation presenter journey

## Status and intent

Design captured from Will's approved conversational direction on September 12,
2026, including the clarification that his real mailbox represents Supplier
Alpha. Written specification awaiting review. This document is not an
implementation, deployment, permission grant, or claim of successful delivery.

The presenter demonstrates a connected business story: receive a supplier delay,
investigate its impact, choose a response, obtain independent approval, and send
a real, reviewed supplier email. Preserve the current planner-language cards,
Outlook/Teams source icons, bottom-of-card provenance, USD formatting, and the
contrast between traditional Power BI investigation and AI-assisted synthesis.

## Mailbox roles

| Role | Demo mailbox | Use |
| --- | --- | --- |
| Supplier Alpha, played by Will | will@willmacdonald.com | Sends the disruption and receives Alex's response |
| Alex, material planner | agent@willmacdonald.com | Receives the disruption; reviews and explicitly sends the response |
| Taylor, Finance Approver | Existing provisioned Taylor identity | Independently approves or rejects the proposed spend in the web app |

The new journey replaces the seeded `rl-supplier-alpha@willmacdonald.com`
sender binding with Will's mailbox for new inbound cases. It must not relabel
old messages, rewrite saved evidence, rename Will's directory identity, or
silently change the sender shown by Outlook. Runtime addresses and identity
bindings remain deployment configuration, not hard-coded authorization rules.

## Presenter walkthrough

1. Will sends a clearly marked fictional RL-001 disruption email to Alex.
2. In the app, Alex clicks **Check for supplier disruptions**. Work IQ discovers
   and reads the actual message; a notification offers **Review disruption**.
3. Alex reviews the source and creates a case from that email. The **What
   changed?** card remains recognizably like the existing card. Its excerpt,
   sender, received time and Outlook link refer to this newly received message.
4. **Understand the disruption** and **Investigate responses** combine this
   evidence with the relevant fictional operational data in Fabric.
5. In **Choose a response**, Alex compares options and selects one. Selection is
   visibly confirmed; it is not approval or execution.
6. In **Review and approve**, any required Finance review goes to Taylor's
   separate authenticated session. Taylor's rejection returns a reason to Alex;
   approval enables Alex's separate final approval of the unchanged proposal.
7. **Execute mitigation plan** shows actions appropriate to that option. Alex
   reviews the supplier email and explicitly clicks **Send email**. Will opens
   the real received message in his own inbox.

## Bounded designs and order of work

- [Independent approval and five stages](2026-09-12-independent-approval-and-five-stage-flow-design.md): implement and review first; prevents apparent approval from standing authorization.
- [Presenter-controlled inbound discovery](2026-09-12-presenter-controlled-inbound-disruption-design.md): actual source binding and duplicate-safe case creation.
- [Option execution and reviewed email](2026-09-12-option-execution-and-reviewed-email-design.md): depends on exact approved proposals; verify draft/send capability before enabling real sending.

Each implementation task receives Codex review before the next task. Written
design review precedes detailed implementation plans. Do not bundle unfinished
stages into a deployment and describe the whole journey as complete.

## Contract amendments

For new cases explicitly using this workflow version, replace automatic Taylor
standing authorization with independent Finance review when required. Existing
historical approval evidence remains unchanged. The legacy combined-only action
set does not define the actions for new standalone response options.

The old demo contract's prohibition on external sending receives one narrow
exception: authenticated Alex may explicitly send reviewed fictional-demo email
to the configured Supplier Alpha mailbox (Will). Simulation still cannot send.
Purchase-order changes, financial commitments, arbitrary recipients, automatic
replies and unattended mailbox monitoring remain out of scope. Required tenant
consent is a separate setup gate, not inferred from approval of this design.

## Acceptance and review

Completion requires a recorded walkthrough from a fresh inbound email through
exact-source citation, separate Taylor review (including rejection), Alex's final
approval and an email actually received by Will. Test approval and execution
differences across supported options, repeated clicks, reloads, stale proposals,
expired sessions and ambiguous send results. Keep simulated operational outcomes
visibly separate from real email activity.

Design self-review: checked against the current sender filter, Alex-only auth
composition, Taylor standing authorization, combined-only planner, fixed
simulation outcomes, and original no-external-send contract. These are explicit
implementation changes, not capabilities already verified in production.
