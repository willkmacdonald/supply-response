# Response selection feedback

**Goal:** Make choosing a response visibly succeed and provide a clear next step to the approval tab.

**Architecture:** Keep selection in the existing workspace state. OptionComparison renders the selected card and a navigation-only callback; InvestigationFlow activates and focuses the approval tab. No API or approval behavior changes.

**Tech:** React, TypeScript, CSS, Vitest, browser verification.

## Constraints

- Highlight the selected card, label its button “✓ Selected,” and distinguish selection from recommendation and approval.
- Continue to review and approve only navigates; it must not submit, approve, send mail, or execute.
- Preserve disabled options, operation locks, keyboard navigation, and selected state across tabs.

## Implementation and verification

1. Reproduce missing visible feedback with failing interaction tests.
2. Add selected styling, text feedback, and continuation in the selected card.
3. Connect continuation to the fourth tab with keyboard focus.
4. Run the frontend suite and production build; inspect desktop and narrow-screen browser behavior.
5. Report local and deployed verification separately.
