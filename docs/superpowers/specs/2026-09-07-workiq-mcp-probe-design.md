# Temporary Work IQ MCP authentication probe

## Approved purpose

Verify whether the deployed Supply Response API can fetch the previously
discovered Jordan quality post through Work IQ MCP using Alex's existing
delegated sign-in and the API's existing on-behalf-of (OBO) credentials.
The user authorized implementation, deployment, one verification, and removal.
This is not the production retrieval fix or another discovery experiment.

## Selected approach

Add a temporary authenticated API probe and a minimal, explicitly invoked browser
control that uses the application's existing authentication provider. This tests
the actual application identity and OBO exchange. Repeating the native CLI test
would test a different client; exporting a browser token to an operator script
would introduce unnecessary credential handling.

## Boundaries

- Accept only the real `AuthenticatedActor` produced by the configured
  `AuthService`, with the existing exact Alex tenant, object, persona and roles.
  Reject missing authentication, other actors, and fallback/test mode.
- Fetch only the approved quality post. Resolve its exact tenant/team/channel/
  message binding from the local deployment record when preparing the probe.
  Do not accept caller-supplied URLs, resource paths, questions, or tool names.
- Use the existing `WorkIQAgent.Ask` OBO exchange, then the fixed HTTPS
  `https://workiq.svc.cloud.microsoft/mcp` endpoint. No direct Graph fallback,
  new consent, roles, billing settings, or client credentials.
- Use only MCP initialization and the `fetch` tool. Do not invoke discovery,
  conversational `ask`, mutation tools, or any other source.
- Require an explicit POST from the signed-in browser. Merely loading or
  refreshing the application must not run the probe or create a Case.
- Allow at most one attempt per process, claimed before OBO or network work,
  with concurrent attempts rejected. Deploy only with a verified single replica
  and single worker. A fixed UTC expiry, chosen immediately before deployment,
  limits availability to a maximum 30-minute window; it must not slide on restart.
  The per-process latch is not a durable tenant-wide exactly-once guarantee.
  If the replica restarts or scales during the experiment, stop and retire the
  probe instead of automatically running it again.
- Bound total request time, response bytes, and JSON nesting. Disable HTTP
  redirects and retries. A failed attempt consumes the allowance.

## Result and data handling

Return only allowlisted stages, numeric HTTP status where available, and
validation booleans: authenticated Alex, OBO succeeded, MCP initialized,
fetch succeeded, exact message identity, expected author, valid source timestamp,
nonempty body, and expected channel/source-link identity.

Do not return or log tokens, authorization headers, raw errors, message bodies,
excerpts, source URLs, or arbitrary upstream fields. Keep upstream responses only
as request-local variables, with no diagnostic response store, telemetry capture,
files, database records, or browser persistence. Ensure exceptions and automatic
instrumentation do not expose those values. Do not change normal analysis,
evidence validation, citation rules, or the existing fail-closed behavior.

## Verification

Write failing tests first for missing/incorrect identity, non-live mode, expired
window, concurrent and repeated attempts, fixed request target/tool, redirects,
bounded responses, protocol errors, upstream error redaction, and positive
message validation. Exercise the actual authentication dependency boundary as
well as the probe's request/response validation.

Run relevant backend and frontend tests and existing deployment validation.
After deployment, verify the immutable revision, single worker/replica, expiry,
and unchanged roles. Run the explicit browser probe as Alex once and inspect
only its safe result. Success requires the app's OBO token to retrieve the exact
post through MCP; configuration checks or CLI success alone do not count.

If Alex must sign in, request that interaction. If the probe cannot be used within
its window, remove it rather than leave a diagnostic endpoint waiting indefinitely.
Any additional attempt or permission change requires a separately agreed next step.

## Mandatory cleanup

Remove the temporary endpoint, browser control, wiring, expiry configuration,
and probe-specific implementation/tests after the attempt, whether it succeeds
or fails. Preserve a non-sensitive outcome record and a regression test asserting
the endpoint/module are absent. Validate and deploy the cleanup; verify the
probe-bearing revision is inactive and receives no traffic, the current endpoint
returns 404, and ordinary health remains good. Do not call the task complete
until deployed cleanup is verified. No Git push is included.
