# Work IQ response-shape diagnostic

Approved by the user on 2026-09-07 following the response-to-evidence audit.

## Purpose

Capture the structure of failed supplier and quality Work IQ normalization without
capturing the contents. Current live requests complete, but their data parts do
not satisfy the local `facts` assumption. Text plus otherwise valid evidence also
fails the existing downstream collection check. Neither check is changed here.

## Boundary

- Only normalization failures emit a diagnostic, at most once per source kind per
  application process. Successful responses emit nothing.
- Log only a fixed source-kind label, approved field names, JSON types, container
  counts, and explicit truncation. No primitive values, string lengths, unknown
  field names, text, IDs, URLs, timestamps, headers, prompts, tokens or exceptions.
- Redact unknown keys; bounded traversal may retain their child structure using
  the same allowlist. Never parse strings as JSON or expose status-message text.
- Traverse at most 128 nodes, 12 levels and two array/unknown-key examples per
  container. Bound the serialized record to 8,192 characters, falling back to a
  fixed truncation record if exceeded. No raw response is persisted.
- Keep requests, authentication, normalizer decisions, evidence policy and public
  errors unchanged. The original normalization exception must be re-raised.
- Remove the diagnostic hook when the live shape is captured and the mapping
  correction is verified. This deployment is diagnostic, not a claimed fix.

## Verification and deployment

Test privacy with secret sentinels in values and keys, nested containers and
JSON-looking strings. Test all primitive types, traversal/output limits, original
exception preservation, both source labels, failure-only emission and per-process
deduplication. Run Work IQ regressions and the full Python/web checks. Independently
review the change, then use the existing approved Azure validation/deploy workflow.
Use one Alex analysis attempt if an authenticated UI session is available; otherwise
request only that attempt. Do not replace Alex with the admin identity.
