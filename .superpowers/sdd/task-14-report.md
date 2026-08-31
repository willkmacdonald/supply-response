# Task 14 report — single-tenant Entra authentication and persona roles

Status: **DONE_WITH_CONCERNS**

Local implementation is complete and verified. Live app registration, service-principal creation/update, permission consent, persona app-role assignment, and live `--check` execution were intentionally not performed; they remain approval-gated.

## Delivered

- Two `AzureADMyOrg` manifest templates: confidential **Supply Response API** and public **Supply Response Web** SPA.
- API delegated scope `access_as_user`; exact user roles `material_planner`, `response_approver`, `quality_approver`, and `finance_approver`.
- `WorkIQAgent.Ask` requested only by the API; the Web requests only the API delegated scope.
- Fail-closed, idempotent scripts with separate `--dry-run`, `--check`, and `--apply` modes. Local fixture mode makes no Azure/Graph call. Deployment values are written only to ignored `infra/entra/.env.tenant` with mode `0600`.
- Strict RS256 API token validation for exact issuer, audience, lifetime, tenant, object ID, app roles, and immutable persona binding. Metadata/JWKS are size/key-count/TTL bounded with one refresh on key-ID miss.
- `AuthenticatedActor` carries the original assertion only in a redacted, non-dataclass/non-JSON `UserAssertion`; immutable Decision identity snapshots contain tenant ID, object ID, persona ID, roles, UPN, and display name without a token.
- Tenant-specific MSAL redirect/silent flow, session-storage cache (never local storage), delayed child mounting until redirect initialization, and per-request dynamic bearer attachment. No-Entra fallback remains operational.
- `PyJWT[crypto]>=2.10,<3`, `@azure/msal-browser>=5.20.0 <6`, and `@azure/msal-react>=5.7.0 <6` with updated lockfiles.
- Deployment runbook at `docs/deployment/personal-tenant.md`. Live FastAPI dependency composition/route enforcement is explicitly isolated for Task 17.

## RED → GREEN evidence

1. Backend RED: `tests/auth/test_token_authorization.py` failed collection with `ModuleNotFoundError: apps.api.app.auth`.
2. Backend GREEN: adversarial JWT/JWKS/persona/snapshot tests passed, including algorithm confusion, signature failure, scalar-audience enforcement, exact delegated scope and role sets, wrong issuer/tenant, guest identity provider, UPN-only lookup, malformed/oversized tokens, duplicate/oversized keys, successful rotation, TTL refresh, assertion lineage, and redaction.
3. Manifest/script RED: 7 tests failed because `infra/entra` artifacts did not exist.
4. Manifest/script GREEN: manifest/PATCH contracts, fixture dry-run/check, all-boundary restart recovery, exact drift detection, fail-closed input, persona-object-ID, and ignore-file tests passed.
5. Frontend RED: missing `AuthProvider`/MSAL modules and access-token-provider API; later focused RED caught permissive scope parsing and premature child mounting.
6. Frontend GREEN: 28 tests passed across AuthProvider, API client, and existing App behavior, including initialization rejection and concurrent interaction-required acquisition.

## Independent-review corrections

The six Important findings and one Minor finding from the independent review were closed test-first:

- Graph read-only `appRole.origin` is absent from both the manifest and generated PATCH payload; fake-Graph apply tests inspect every PATCH body.
- `authenticate()` no longer accepts an alternate OBO assertion. The successfully validated inbound token is the only retained assertion.
- Audience is an exact scalar UUID, `scp` is exactly `access_as_user`, and each bound persona must present exactly its fixed role set.
- Provisioning persists each created client ID immediately in a `0600` state file marked `INCOMPLETE`. Injected failures after all six mutation boundaries prove retries reuse the same two applications; only final exact validation marks the state `COMPLETE`.
- Registration checks compare canonical exact scopes, permissions, redirects, and complete role shapes. Persona checks reject excess assignments for Alex, Jordan, or Taylor.
- MSAL initialization failures render a recoverable sign-in action. Concurrent silent acquisition remains concurrent while interaction-required redirects are single-flight.
- Shell and SPA redirect validation now share the same HTTPS/loopback, no-query, no-fragment, single-trailing-slash normalization contract.

## Second independent-review corrections

The three remaining Important findings and Minor redirect-contract finding were closed test-first:

- Exact Graph validation now projects every intended writable app-role and delegated-scope field plus `api.acceptMappedClaims`, while deliberately excluding Graph's response-only `appRole.origin`. Graph-shaped fake responses include `origin`; writable and security drift still fail closed.
- Authentication recovery reruns MSAL initialization and redirect handling. Initial-failure-then-success, repeated initialization failure, and login-redirect failure tests prove the UI remains recoverable without unhandled rejections.
- Apply tests can select only an absolute executable named `supply-response-fake-az` that passes an exact adapter handshake. State override and fault injection require fixture mode or that validated adapter, every Azure command is dispatched through it, the final validation bypass was removed, and realistic persisted Graph responses must validate before state becomes `COMPLETE`.
- Provisioning and SPA configuration both reject authorities that URL parsing would rewrite, including uppercase hosts and default ports, while preserving their shared single-trailing-slash normalization.

## Verification

- Auth/artifact suite: **63 passed** after the second correction pass.
- Full non-live Python suite: **442 passed, 12 skipped**. Its locked TMDL validator required approved access to public NuGet. One pre-existing Starlette/httpx deprecation warning remains.
- Frontend focused suite: **3 files, 33 tests passed** after the second correction pass; production TypeScript/Vite build passed.
- Changed Python scope: Ruff check/format passed; Pyright **0 errors, 0 warnings**.
- Bash: `bash -n` passed; `shellcheck` was unavailable. JSON parsed with `jq`; fixture dry-run/check and fake-Azure apply/retry tests passed.
- `uv lock --check` passed; Python sdist/wheel build passed.
- `pip-audit`: no known vulnerabilities. `npm audit --audit-level=high`: 0 vulnerabilities.
- `git diff --check`: passed.
- Repository-wide Ruff/Pyright remain outside this task's acceptance gate because the committed baseline has the previously documented `services/policy/thresholds.py` E402 and unrelated historical typing errors; all changed Python scope is clean.

## Self-review

- No client secret, tenant/client/object ID, UPN, access token, or real assignment appears in tracked deployment artifacts.
- No tenant mutation ran. During the second correction's initial RED run, before the fake-adapter selection existed, the old apply recovery test accidentally selected the installed Azure CLI and performed read-only active-account, organization, and Work IQ service-principal lookups; it failed at the Work IQ lookup before reaching any mutation. This was disclosed immediately, and all subsequent apply/recovery tests are isolated behind the validated fake adapter.
- Scripts require exact UUIDs, active-tenant equality, explicit `willmacdonald.com` confirmation, unique enabled permission/role resolution, and distinct persona object IDs. They do not resolve personas by UPN or display name.
- Token validation pins RS256 and tenant-specific metadata/JWKS URLs, rejects non-home identity providers, bounds inputs/caches, and never logs bearer data.
- Existing fallback composition and unrelated core behavior were preserved.

## Approval-gated next action

With explicit approval for the target `willmacdonald.com` tenant:

1. Supply the real expected tenant UUID, Work IQ resource app UUID, and exact SPA redirect URI.
2. Run `infra/entra/configure.sh --apply` to create/patch the two registrations and service principals.
3. Review and grant delegated consent for API `WorkIQAgent.Ask` and Web `access_as_user`.
4. Supply Alex/Jordan/Taylor immutable object IDs and run `infra/entra/assign-personas.sh --apply`.
5. Separately approve and run both live `--check` commands after propagation.

No client secret is needed for API access-token validation. A future Work IQ OBO exchange needs an approved, securely managed confidential-client credential (prefer certificate/federated assertion), never a committed secret.

## Official sources

- Microsoft identity access-token claims: <https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference>
- Token/claim validation: <https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation>
- Microsoft Graph application resource and `AzureADMyOrg`: <https://learn.microsoft.com/en-us/graph/api/resources/application?view=graph-rest-1.0>
- App roles and token `roles` claims: <https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps>
- App-role assignment API: <https://learn.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignedto?view=graph-rest-1.0>
- Azure CLI app permissions: <https://learn.microsoft.com/en-us/cli/azure/ad/app/permission?view=azure-cli-latest>
- MSAL.js cache behavior: <https://learn.microsoft.com/en-us/entra/msal/javascript/browser/caching>
- Silent then interactive acquisition: <https://learn.microsoft.com/en-us/entra/msal/javascript/browser/acquire-token>
- OAuth 2.0 OBO: <https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow>
