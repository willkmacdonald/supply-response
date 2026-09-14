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
milestones. Live deployment verification will be recorded separately below.
