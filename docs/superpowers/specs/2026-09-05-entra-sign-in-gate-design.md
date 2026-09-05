# Entra Sign-In Gate Design

## Problem

The deployed application initializes the Case workspace before an Entra account is active. In a fresh browser session, the first protected API call therefore fails with `No authenticated Entra account is active`. Although `AuthProvider` already exposes `signIn()`, the application does not render a control that invokes it, leaving a legitimate user unable to begin the live demonstration.

## Scope

Add a small authentication gate around the existing Case workspace UI. This change does not alter Entra registrations, roles, token validation, API authorization, fallback behavior, or the domain workflow.

## Design

`App` will read the existing authentication context before constructing the authenticated Case workspace experience.

- In fallback mode, render the Case workspace exactly as it does today.
- In Entra mode with no active account, render a clear `Sign in as Alex` action and do not initialize or call protected Case APIs.
- The action delegates to the existing `AuthProvider.signIn()` redirect flow and requests only the existing API scope.
- After Microsoft redirects back and `AuthProvider` resolves an active account, render and initialize the normal Case workspace.
- Existing authentication failures remain recoverable through the provider's current retry behavior.

The workspace implementation will remain in its own component so the authentication decision occurs before `useCaseWorkspace()` is invoked. This preserves React hook ordering without allowing the protected hook to run behind the gate.

## Error and Safety Behavior

The gate will not accept injected tokens, test-only authentication shortcuts, alternate tenants, or a fallback identity in live mode. It will not automatically redirect on page load; the explicit button makes the identity transition visible during the demonstration and avoids redirect loops.

## Verification

Test-first coverage will prove:

1. Entra mode without an account shows the sign-in action and does not initialize the Case workspace.
2. Selecting the action invokes the existing Entra sign-in flow.
3. Entra mode with an active account renders the Case workspace.
4. Fallback mode remains unchanged.

After local tests pass, rebuild and redeploy the immutable Container App revision, rerun the user-context-free live smoke gate, and complete the Alex-authenticated Work IQ, decision, execution, observation, and Power BI journey.
