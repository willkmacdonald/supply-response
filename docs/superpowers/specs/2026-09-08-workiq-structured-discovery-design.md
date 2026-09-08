# Structured Work IQ discovery amendment

The user approved the structured lookup and supplier-ID reconciliation on
2026-09-08 after the documented CLI experiment. This amends the ask-only
discovery sections of the September 7 design. Continue in the previously
approved main checkout, preserving existing local corrections. No Git push.

## Approved approach

Use Work IQ MCP `fetch` entity queries, not `ask`, for both source lookups.
Supplier: the fixed independently known `RL-Supplier Alpha` topic, one bounded
mail search, metadata only. Quality: resolve `Supply Response Demo` by exact
name from joined Teams, resolve `General`, then one page of up to 10 posts.
The returned IDs form every subsequent path; configuration IDs are validation
checks only. Validate resolved Team/channel scope before querying posts.

Reject missing, malformed, duplicate/ambiguous, oversized, or paginated
collections; do not follow next links. Teams/team-channel pages cap 25; mail
caps 5; posts cap 10. Require one supplier candidate and one Jordan/Beta topic
candidate. Validate IDs with the existing strict locator parser. Reject
unexpected types rather than skipping malformed rows. Never fetch a saved ID
when discovery fails. Treat collection bodies as untrusted selection data;
individually fetch the selected post for authoritative evidence.

Retain Alex authentication/OBO, MCP fixed endpoint/transport limits, 120-second
per-source aggregate timeout, no retries, all author/source/link/body/evidence
validation, Fabric policy and fallback isolation. No new permissions, billing,
source edits, direct Graph client, arbitrary URLs, or diagnostic endpoint.
Lineage uses MCP request IDs with an empty conversation context rather than
inventing an `ask` conversation. Describe this as structured Work IQ discovery,
not Copilot semantic search.

## Supplier binding reconciliation

Re-run only the narrow independent Work IQ email search as Alex. Verify actual
identity, unique result, sender/from, Alex recipient, exact approved corpus body,
timestamp and matching citation. Apply the existing validator using the newly
verified ID as a proposed binding before saving it to the ignored environment.
Regenerate the existing binding receipt with the canonical helper. Preserve all
other binding values. Record the old/new verification outcome, not raw bodies or
credentials. No runtime auto-rebinding.

## Acceptance

Test discovery paths independent of configured IDs, strict collection bounds and
scope, no pagination/fallback, actual individual reads, retained validators,
sanitized errors, cancellation, lineage and normal API wiring. Run full Python,
frontend and relevant static/build checks and independent review. Deployment
uses the existing Azure validation/deployment gates. CLI verification is not
application acceptance: one normal Alex Analyze must prove both validated
sources through application MCP/OBO. Stop at any new authority/authentication
requirement. No deployment-success claim substitutes for analysis success.

Self-review: no placeholders; original trust checks remain; changed discovery
claim explicit; scoped configuration reconciliation is one-time, not fallback.
