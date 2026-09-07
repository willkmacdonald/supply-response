# App-authenticated Work IQ MCP verification

## Result — 2026-09-07 UTC

The single approved browser request completed with HTTP 200 at stage `complete`.
The deployed API authenticated Alex and used its own configured application OBO
credentials, not the Work IQ CLI identity. All returned checks were true:

- Alex authenticated; OBO succeeded; MCP initialized; fetch succeeded.
- Exact message identity, expected author and expected channel identity.
- Valid source timestamp, nonempty message body and expected source link.

The fixed target was the existing Jordan fictional-demo quality post. No message
body, token or raw upstream response was written to this record. No Graph
fallback was used and no permissions, billing or normal analysis behavior changed.

Revision `ca-sr-demo--0000012` used immutable image digest
`sha256:9dd4f350f8751f103ea9ba0c0b905cfcb36b27b8ae4ceb60a2faf752bfec9e53`.
Immediately before and after the request, exactly one ready/running replica
`ca-sr-demo--0000012-647b444449-s5cn9` was observed, with zero restarts.
The request was made at approximately 21:39 UTC within the fixed 21:30–22:00 UTC
window. The button was clicked once; no retrieval retry was made.

## What this proves

The actual application can retrieve this known Teams message and its content
through Work IQ MCP under Alex's delegated identity. The earlier successful CLI
fetch is therefore reproducible using the application's existing credentials.

This is a known-source retrieval test, not a new discovery test or a fix to normal
analysis. Production discovery, retrieval integration and evidence mapping still
need a separately approved implementation. No Graph substitution is implied.

## Retirement

The temporary modules, API route, browser view and diagnostic-only tests have
been removed locally. The four modified runtime files are restored exactly to
the pre-probe `c88bf2f` versions. A retained regression checks module/view absence,
OpenAPI absence, GET 404 and POST rejection (405 with the existing packaged SPA
catch-all; 404 without static assets). The approved plan's POST-404 expectation
was corrected to baseline routing behavior instead of changing normal runtime.
Both original regression
assertions failed before removal as expected.

Cleanup commit `bc3f11a` deployed successfully through the approved apply/smoke
workflow. ACR build `ch13` succeeded. Revision `ca-sr-demo--0000013` is the sole
active revision, Healthy/Running, latest/ready and receiving 100% of traffic.
The diagnostic revision `ca-sr-demo--0000012` is inactive, Stopped, with zero traffic.
The cleanup image digest is
`sha256:109d0f6c58eaeb0e537bd3432b8900fc75164203e09b9ab120c81edf87afc7e4`.

Live checks confirmed the retired path returns GET 404 and POST 405 and is absent
from OpenAPI. Health passed in live Fabric SQL mode at schema version 12; the
approved Fabric/Foundry smoke passed without a delegated user operation. The
managed identity and its exact three existing Azure role assignments are unchanged.
The named deployment environment was verified. No Git push was performed.

Verification: full Python suite and package build passed; all 51 frontend tests
and production build passed. Three final retirement regressions, scoped static
checks and independent cleanup review passed. The existing Starlette deprecation
warning and expected live-test skips remain unrelated.
