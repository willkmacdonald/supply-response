# Presenter header and stage tabs — verification

## Scope

Implements the approved September 12 presenter design in the existing React
frontend. The case header explains the AI-assisted planning story. Only the
nine-card investigation becomes three tabs, each with three vertically stacked
cards. Outlook and Teams product icons accompany their existing trusted source
actions. Data contracts, calculations, report destinations, permissions,
authentication, and approval behavior are not changed.

## Review checkpoints

- Header/tabs: `7d1f1cf`, followed by `97c9bbf`. Independent review found and
  verified the fix for keyboard roving focus: moving focus does not select a
  different stage, and exactly one tab remains in the tab sequence.
- Source icons: `c65fca0`, followed by `8a6252b`. Independent re-review passed
  after adding complete Teams safe-link assertions, validated test fixtures,
  and a single shared classification for link text and icon selection.
- Integrated final review: approved `ab62899..8a6252b`, with no Critical,
  Important, or Minor findings. Review covered the combined feature and
  surrounding lifecycle, source, approval, and layout behavior.

## Browser acceptance

Local preview: `http://127.0.0.1:5190/.tmp/presenter-preview.html`.

The preview server is running locally. Opening it in the Codex browser was queued
successfully; the handoff also provides the direct local link.

This uses the actual application components and styles with an isolated,
simulated analysis fixture. The preview explicitly labels its data and source
links as simulated. It performs no live retrieval, case creation, approval,
or Microsoft service writes. Product-link rendering can be checked here; real
Outlook/Teams destination access is not established by this fixture.

Browser acceptance passed at `c65fca0` and was repeated successfully at final
implementation commit `8a6252b` in Chromium at 1440px and 390px:

- All three tabs show exactly their three original cards in the required order.
- Cards stack vertically with equal available width and natural content height.
- Inactive panels remain mounted, hidden, and inert; no page-wide overflow.
- Keyboard arrows/Home/End move focus; Enter/Space select; roving tabIndex is
  independent of selection.
- Open source details and a selected response survive tab round trips.
- Tab/selection changes make no requests and do not change the URL.
- Outlook/Teams images load locally beside the exact expected source links.
- Source footers remain last; disabled approval stays disabled.
- Fallback mode retains the global sample-data notice and renders no live icons.
- No browser exceptions or external network requests occurred.

The first harness run matched several valid fallback notices instead of only
the global one. Scoping that assertion to `.analysis-context` corrected the
test ambiguity; the application did not need a change.

Visual inspection covered desktop screenshots of all stages, the mobile header
and tabs, source-action close-ups, and recommendation/decision cards. Icons and
text are aligned, warnings remain beside their claims, and notes remain legible.
The comparison card retains its full existing option list; this change does not
remove options to shorten it.

Local harness: `.tmp/presenter-browser.cjs`; captures under
`.artifacts/presenter-tabs/`. These are ignored local verification artifacts,
not shipped application code. The harness uses the existing Node Playwright
dependency because the Python Playwright package is not installed.

## Release boundary

Parent verification on `8a6252b`: `npm test` passed all 314 tests in 21 files;
`npm run build` passed TypeScript and Vite production compilation and emitted
both local product SVGs. `.tmp/presenter-browser.cjs` passed all four desktop,
phone, configured-live, and fallback combinations.

These changes are not deployed to Azure. A local build or layout preview is not
proof of a cloud release, live-service health, report access, or source retrieval.
The existing deployed demo is unchanged by this verification.
