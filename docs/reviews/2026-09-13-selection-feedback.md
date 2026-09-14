# Response selection feedback

## Approved behavior

Choosing a response highlights its card, changes the button to “✓ Selected,”
and exposes “Continue to review and approve.” Continuing activates and focuses
the fourth tab. Neither action submits, approves, sends mail, or executes a plan.
Recommendation and selection remain distinct.

## Verification

- Regression reproduced before the fix: selected styling/text did not exist.
- 348 frontend tests pass across 24 files; production TypeScript/Vite build passes.
- Added tests for replacing a selection, continuation, focus, persistence across
  tabs, blocked options, busy state, and absence of operation calls.
- Desktop 1440px and mobile 390px browser checks passed with the real React
  components and simulated fixture data. Screenshots inspected; no horizontal
  overflow, JavaScript errors, or mutation requests.
- Independent reviewer found no actionable issues in the scoped change.

This is a selection/navigation correction, not completion of execution or email
milestones.

## Live release proof — 2026-09-14 UTC

- Source `0347765`; ACR run `ch1m`; live revision `ca-sr-demo--0000030`.
- Immutable digest `sha256:e269e7160d40b916b0761a715424b8f6cc6a80f5446bd7649bf46d7f6ddf96b1`.
- Healthy, Running, Provisioned, latest-ready, readiness passed, 100% traffic;
  scale0–2 and the existing three resource-scoped runtime roles unchanged.
- Alex's real authenticated browser reopened case
  `RL-CASE-bcbb8740-c770-42fd-aa67-981d08b66383`, analysis
  `RL-ANALYSIS-aa9e5be1-6d28-491e-a179-0eb4752bf00c`.
- Clicking Expedite visibly highlighted its card and showed “✓ Selected,”
  confirmation text, and Continue. Live screenshot inspected.
- Continue activated and focused tab4, which displayed $22,500 and the separate
  “Submit for Finance review” button; no submission was made.
- Restored Combined and continued again: original $24,750 proposal remained
  waiting for Taylor, with original review
  `RL-FINANCE-e5ef2083-55ae-4605-9756-db242d12149b`.
- No new case, analysis, approval, email or execution action was performed.
