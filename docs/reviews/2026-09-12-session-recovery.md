# Session recovery acceptance

## Scope and diagnosis

An old browser tab failed to initialize the workspace and list cases; a private
sign-in worked. A browser trace showed authorization followed by `/auth/callback`
loading the full dashboard and `/api/runtime`, but no `/api/cases` request.
This isolated the failure to browser sign-in renewal rather than missing case data.

The installed MSAL Browser version is 5.20.0. Its documented redirect bridge
must handle the callback before the application's authentication provider starts.
The prior entry point started the full application on every path. It also let
non-interaction-required token errors fall through to generic workspace errors.

Reference: [Microsoft redirect-bridge documentation](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/redirect-bridge).

## Correction and review

Implementation `5bbb75b` routes the exact configured callback to the actual MSAL
bridge, leaving normal application startup separate. Renewal failure offers
**Sign in again**, preserves mounted planning state while hiding/disabling it,
and forwards the original case URL to interactive recovery. No failed GET/POST
is sent without a token or replayed automatically. A full-App regression also
caught token-provider registration ordering; that was corrected before release.

Independent session_recovery_review approved spec compliance and release quality
with no findings. Parent inspected code, fresh tests/build, and browser screenshots.

## Completed local checks

- Baseline: 292 frontend tests passed before implementation.
- Corrected: 305 tests in 19 files passed, including callback isolation, safe
  errors, concurrency, late successful token after another request failed,
  blocked GET/POST, explicit/deduplicated recovery, initialization/fallback,
  current URL and mounted state preservation, and full-App recovery display.
- Production TypeScript/Vite build passed; application and callback startup
  are split into separate chunks. No dependency version or registration change.
- Actual installed MSAL bridge tested in Chromium with synthetic responses,
  against both development and production bundles: silent BroadcastChannel
  handoff without App imports/API calls; full redirect returns to exact
  synthetic case+analysis URL; malformed callback displays no raw details.
- Full App with a controlled failing AuthClient verified at 1280px and 390px:
  clear recovery notice, zero API requests, no visible generic workspace error,
  no horizontal overflow, and original URL forwarded by the recovery click.
- Screenshots inspected: `.artifacts/session-recovery/recovery-1280.png` and
  `recovery-390.png`. The browser harnesses are retained in ignored `.tmp/`;
  fixture files under `apps/web/.tmp/` are not application entry points.
- Python Playwright was unavailable in both local and bundled runtimes, so the
  existing project Node Playwright runtime supplied the same Chromium checks.

These are controlled browser tests, not a claim that a four-day-old Microsoft
session was reproduced or that the user's existing session has been renewed.

## Release status

Azure validation and the approved guarded deployment completed for the existing
resource scope. Release `be45c4d`, ACR build `ch1g`, revision
`ca-sr-demo--0000026` is Ready/Running with 100% traffic. Image digest:
`sha256:51d21a6e997e198867af0c8c8e0cef19bb4940cf4390d0f59a81f742507e5af2`.

- `azd show` completed; the project intentionally has no AZD service declarations.
- Public health and runtime returned success: live/Fabric SQL/schema12 and four
  capabilities ready. This does not independently exercise Work IQ or Foundry.
- Existing managed identity, its three resource-specific roles, and 0–2 scale
  remain unchanged.
- Actual deployed callback passed the same three Chromium checks above using
  synthetic responses in isolated browser storage. No Microsoft token exchange,
  dashboard startup, or API requests occurred in these checks.
- Public deployed bundles `index-DUUx6KrO.js` / `application-DhINkC1k.js` were
  inspected and contain the callback guidance, recovery notice and button.

No reporting, source-data, permission, case, analysis, decision, or action changes
are included. Real Microsoft expired-session recovery remains unobserved; the
user's successful private sign-in predates this release and is not proof of it.
