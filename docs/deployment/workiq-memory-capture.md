# Temporary Work IQ answer inspection

User-approved diagnostic only; not a correction of live evidence validation.
Remove `integrations/workiq/memory_capture.py`, its startup hook in `main.py`,
and the `_send_captured` wrapper in `client.py` after the inspection, then
redeploy. No public route, role, source, billing or database changes are required.

## Boundary

- Off by default. One explicit arm per process, expiring after 30 minutes.
- First successful validated-Alex OBO call reserves the case/analysis pair.
  Only one supplier and one Quality response for that pair can be retained.
- At most four artifacts/eight parts, 8,192 characters per final text part;
  recognized `application/vnd.ms-workiq-reference` metadata only, with
  allowlisted citation fields. Unknown data parts are counted, not copied.
- At most 65,536 serialized bytes per response. Oversize projections return a
  fixed marker. Common bearer/JWT and credential query strings are redacted.
  This is not a general-purpose secret detector; only the approved final answer
  and citation metadata may enter the projection.
- No headers, tokens from authentication, status/chain-of-thought messages,
  prompts, raw bodies, files, logs or telemetry events are emitted by capture.
- Held references clear after one `take`, `discard`, shutdown, or within one
  second of the ten-minute deadline measured from the first reserved call.
  Core dumps are disabled. This is reference release, not secure RAM zeroization.
- The Linux abstract Unix socket creates no filesystem entry and opens no TCP
  listener. Kernel peer credentials require the application's exact UID.
  Authorized Azure container exec supplies operator access; no new role grants.

## Operator procedure

1. Verify the ready revision, replica and container. Arm **only one replica**.
   The deployment may scale to zero; do not arm an old revision. If multiple
   replicas are active, do not arm all of them or change scaling without approval.
2. In that exact container run `python /app/integrations/workiq/memory_capture.py
   status`, then `arm`. These commands return state only.
3. Ask Alex to run Analyze once. The existing 503 may still occur.
4. Poll `status`. Once ready, run `take` once through the same container-exec
   connection. Inspect stdout in memory. **Never redirect/tee the output, use the
   deployment safe-command capture wrapper, or enable shell tracing/CLI debug.**
5. `take` clears the stored pair even if transmission fails; no retry retention.
   If the capture expires or the replica restarts, the evidence is lost. Do not
   collect another pair without explaining the loss and obtaining approval.
6. Record only findings, not response contents. Confirm `spent`; deploy removal.

The existing client response bounds, OBO checks, normalizer and live acceptance
rules remain authoritative. Diagnostic output must never become evidence input.

## Local checks

`uv run pytest -q tests/integration/test_workiq_memory_capture.py`

The stdlib-only `tests/integration/workiq_capture_socket_probe.py` runs in Linux
as UID 10001 with a read-only filesystem and no network. It exercises the actual
abstract socket and verifies the server loop does not retain the serialized pair
after the destructive read, before another command can overwrite that variable.
