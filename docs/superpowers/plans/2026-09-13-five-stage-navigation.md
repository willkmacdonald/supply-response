# Five-stage Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate choosing, approving and executing into clearly labeled tabs without triggering operations through navigation.

**Architecture:** Reuse the existing mounted StagePanel navigation and existing state hook. Move the existing DecisionPanel to stage four and ExecutionPanel/OutcomePanel to stage five. This local UX increment does not activate the new Finance service or change historical approval policy; it must not claim Taylor's interactive workflow exists yet.

**Tech Stack:** React, TypeScript, Vitest/Testing Library, existing CSS.

## Global Constraints

- All five tabs are inspectable; tab clicks are navigation only, never mutations.
- Keep full-width cards stacked vertically and existing selection/form state across tab changes.
- Preserve source links, bottom-of-card provenance, USD totals without cents and per-part prices with two decimals.
- Selecting a response is not approval or execution.
- This change does not send email, grant approval, change backend policy or deploy anything.

### Task 1: Separate approval and execution panels

**Files:**
- Modify: `apps/web/src/components/InvestigationFlow.tsx`.
- Modify: `apps/web/src/App.tsx`.
- Modify: `apps/web/src/components/ExecutionPanel.tsx`.
- Modify: `apps/web/src/components/OutcomePanel.tsx`.
- Modify: `apps/web/src/styles.css`.
- Test: `apps/web/src/components/InvestigationFlow.test.tsx`, `apps/web/src/App.test.tsx`, `apps/web/src/components/ExecutionPanel.test.tsx`, `apps/web/src/components/reportCardLinks.test.tsx`.

**Interfaces:** Existing `CaseWorkspaceState` and ExecutionPanel/OutcomePanel props remain unchanged. No new network calls or state-hook methods.

- [ ] **Step 1: Establish failing navigation tests.** Extend the existing `state()` fixture and import Decision fixture patterns from the existing ExecutionPanel tests. Test this transition before changing production code:

```tsx
it("separates choosing, approving and executing without operations", async () => {
  const input = state();
  render(<InvestigationFlow state={input} />);
  expect(screen.getAllByRole("tab").map(tab => tab.textContent)).toEqual([
    "1. Understand the disruption", "2. Investigate responses", "3. Choose a response",
    "4. Review and approve", "5. Execute mitigation plan",
  ]);
  await userEvent.click(screen.getByRole("tab", {name: "3. Choose a response"}));
  expect(screen.getByRole("region", {name: "Compare the options."})).toBeVisible();
  expect(screen.queryByRole("region", {name: "Review and approve."})).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", {name: "4. Review and approve"}));
  expect(screen.getByRole("region", {name: "Review and approve."})).toBeVisible();
  await userEvent.click(screen.getByRole("tab", {name: "5. Execute mitigation plan"}));
  expect(screen.getByText("Approve a response in Review and approve before starting its mitigation plan.")).toBeVisible();
  for (const fn of [input.approve, input.reject, input.retryPlanning, input.retryAction, input.startPlayback]) {
    expect(fn).not.toHaveBeenCalled();
  }
});
```

Adapt existing keyboard tests to five tabs: ArrowLeft from first focuses fifth,
End focuses fifth, ArrowRight wraps; manual Enter/Space activation remains.
Existing recommendation tests stay on tab three; rejection, approval and
historical Decision state tests move to tab four. Add tests proving approved
actions/results render only on tab five; rejection has an explicit execution
blocker; switching tabs preserves draft/rejection input and selected option;
execution buttons retain their busy/server-control guards. Update App tests to
click the actual appropriate stage before interacting with its controls.

- [ ] **Step 2: Run RED.**

Run `npm --prefix apps/web test -- components/InvestigationFlow.test.tsx`.
Expected: the new five-stage assertion fails against current three-tab code.

- [ ] **Step 3: Move existing panels without changing their operations.**

```tsx
const stages = [
  {id: "understand", label: "1. Understand the disruption"},
  {id: "responses", label: "2. Investigate responses"},
  {id: "decision", label: "3. Choose a response"},
  {id: "approval", label: "4. Review and approve"},
  {id: "execution", label: "5. Execute mitigation plan"},
] as const;
```

Keep OptionComparison in StagePanel index 2, move DecisionPanel unchanged to
index 3. Import ExecutionPanel and OutcomePanel into InvestigationFlow and use:

```tsx
<StagePanel index={4} activeStage={activeStage}>
  {!state.decision || state.decision.kind !== "approved" ? (
    <section className="panel" aria-labelledby="execution-waiting-heading">
      <h2 id="execution-waiting-heading">Execute mitigation plan</h2>
      <p>{state.decision?.kind === "rejected"
        ? "This response was rejected. Choose a response and obtain approval before starting a mitigation plan."
        : "Approve a response in Review and approve before starting its mitigation plan."}</p>
    </section>
  ) : <>
    <ExecutionPanel busy={state.operation !== null}
      canRetryPlanning={state.caseInstance?.controls.retry_action_planning}
      decision={state.decision} actions={state.actions} drafts={state.drafts}
      retrying={state.operation === "planning"} onRetry={state.retryPlanning} onRetryAction={state.retryAction} />
    <OutcomePanel disabled={state.operation !== null || !state.caseInstance?.controls.start_playback}
      decision={state.decision} actionCount={state.actions.length} playback={state.playback}
      observations={state.observations} starting={state.operation === "playback"} onStart={state.startPlayback} />
  </>}
</StagePanel>
```

Remove the now-duplicate ExecutionPanel and OutcomePanel imports/rendering from
App only; do not move the top-level error/provenance/reopen notices. In
ExecutionPanel replace its step copy with `5. Execute mitigation plan`.
In OutcomePanel remove the numbered `5. Review outcomes` step (use `Review
outcomes`), since results are inside execution rather than a sixth stage.

Change desktop tab grid to `repeat(5, minmax(0, 1fr))`; at max-width 1100px use
three columns, at max-width 640px use two. Retain normal wrapping, visible focus
styles and full-width card stacks. No clipped controls or horizontal page scroll.
Do not add a dummy Taylor review form or a nonfunctional Send button.

- [ ] **Step 4: Run GREEN and complete frontend verification.**

Run `npm --prefix apps/web test`, `npm --prefix apps/web run build`, and
`git diff --check`. Expected: all tests pass, TypeScript and production build
pass. Record test count and output. Parent performs browser verification of all
five panels, keyboard access and desktop/phone widths using synthetic local
fixtures; never approve or send using the live case for a layout check.

- [ ] **Step 5: Commit and independent review.**

```sh
git add apps/web/src/components/InvestigationFlow.tsx apps/web/src/App.tsx apps/web/src/components/ExecutionPanel.tsx apps/web/src/components/OutcomePanel.tsx apps/web/src/styles.css apps/web/src/components/InvestigationFlow.test.tsx apps/web/src/App.test.tsx apps/web/src/components/ExecutionPanel.test.tsx apps/web/src/components/reportCardLinks.test.tsx
git commit -m "feat: separate response approval and execution stages"
```

Report RED/GREEN and exact files. Parent reviews spec compliance and quality,
then records browser proof before declaring the local navigation increment done.

## Self-review and remaining integration

All existing operations remain bound to explicit buttons and unchanged server
controls. This plan covers the five-stage presentation, not the approved Finance
inbox, new-case policy or option-specific real execution. Those remain explicit
separate integration gates; deployed revision28 stays unchanged until accepted.
