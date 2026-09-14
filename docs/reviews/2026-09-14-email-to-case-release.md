# Reviewed email-to-case release

Runtime source `974d4a1`, revision `ca-sr-demo--0000033`, ACR run `ch1q`.
Image `sha256:42524abd04a483b33ded515418929d48b49ab13ef97423dd50e403a9a67ce3a2`.
Latest-ready revision 33 receives 100% traffic; scale remains 0–2. Guarded live
Fabric/Foundry readiness and azd show passed. Existing three resource-scoped
roles are unchanged. No schema migration, permission change or outgoing email.

## Local verification and review

- 360 web tests, production TypeScript/Vite build, desktop 1440/mobile 390 actual
  component interaction with explicitly simulated provider responses passed.
- Backend integration/domain/API/persistence: 661 passed, 18 live-setting skips.
  Existing migration logger pollution requires integration-before-persistence
  ordering; one legacy Alex fixture corrected. No runtime auth relaxation.
- Parent independently reran all 39 new backend tests. Runtime lint/type checks
  passed. Independent review f4b1de8..b6b4764 found no Critical/Important issues.
- Azure preflight/schema/auth/preview/package/policy/static/live-role checks passed.
  Existing-app health transiently timed out before build; later HTTP 200 live
  health passed without bypass, restart, scaling or infrastructure changes.

## Real provider and browser acceptance

User explicitly approved reading Will's 0914-A message body/Outlook link,
saving its source into the demo case, and analyzing it; no mail send.

Work IQ found the same Internet Message-ID before and after Inbox→Archive→Inbox
while its ordinary Outlook ID changed. Original email was restored to Inbox.
This is scoped email-event identity, not a claim that ordinary IDs are immutable.
Ambiguous duplicate physical copies block creation instead of selecting one.

Alex's authenticated revision 33 browser check at 2026-09-14 06:04:32 UTC found
`[Supply Response Demo] RL-001 | Supplier Alpha | Demo run 0914-A`, from
will@willmacdonald.com, received 2026-09-14 05:10:43 UTC. Review displayed the exact
FYI body plus extracted 8,000 affected, 3,000 by air September 6 at $7.50 extra,
remaining 5,000 unconfirmed. No DEMO CORPUS or imperative closing required.

Explicit Create case from this email showed immediate disabled/progress state
and opened `RL-INBOUND-48f48fb45f22d0f5a0c30e4c301aaf887daae09dacfad264b7e4322f75b3105c`
with a separate Analyze disruption action. Analysis was explicitly requested.
Analysis succeeded as `RL-ANALYSIS-b50702a5-5e6c-4655-963b-86c89ce8d993`.
The Understand disruption tab displayed the actual sender, 0914-A subject,
received time and exact FYI body. Required Work IQ checks passed, retrieval at
September 14 06:05 UTC. Stock showed 4,000 available; baseline revenue $955,000,
margin $328,000 and response cost $0 retained whole-dollar formatting.
Open supplier email opened the exact 0914-A message in Alex's Outlook, from
Will to Alex with matching body and current moved/restored locator. Temporary
Outlook tab closed afterward. No old seeded supplier substitution occurred.
Live duplicate retry passed: a fresh mailbox check followed by the same explicit
Create action reopened the identical case and analysis IDs. No additional
analysis was run. The final live screenshot shows the actual sender, subject,
received time, exact excerpt, Outlook icon/link and Work IQ check footer.
The browser was left on this analysis with source details expanded.

[Open verified analysis](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/?caseId=RL-INBOUND-48f48fb45f22d0f5a0c30e4c301aaf887daae09dacfad264b7e4322f75b3105c&analysisId=RL-ANALYSIS-b50702a5-5e6c-4655-963b-86c89ce8d993).

This proves the bounded email-to-case increment, not arbitrary email-language
understanding or the unfinished outbound execution milestone. No Finance
submission, approval, rejection, mitigation execution or mail send occurred.
