# Personal-tenant Entra setup

This repository defines, but does not currently deploy, two single-tenant Microsoft Entra registrations:

- **Supply Response API** — a web API that exposes `access_as_user`, defines four user app roles, and requests delegated `WorkIQAgent.Ask`.
- **Supply Response Web** — a public SPA that requests only `api://<API_CLIENT_ID>/access_as_user`. MSAL supplies the protocol scopes needed for sign-in.

Both manifests use `AzureADMyOrg`. Tenant registration, consent, and role assignment are external mutations and require explicit approval. The checked-in files contain no tenant ID, client ID, object ID, UPN, bearer token, or credential.

## Local validation (safe now)

The dry-run paths consume deterministic fixtures and do not invoke Azure CLI or Microsoft Graph:

```bash
export SUPPLY_RESPONSE_CONFIRM_TENANT=willmacdonald.com
export SUPPLY_RESPONSE_EXPECTED_TENANT_ID=11111111-1111-4111-8111-111111111111
export SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID=44444444-4444-4444-8444-444444444444
export SUPPLY_RESPONSE_API_CLIENT_ID=22222222-2222-4222-8222-222222222222
export SUPPLY_RESPONSE_WEB_CLIENT_ID=33333333-3333-4333-8333-333333333333
export SUPPLY_RESPONSE_REDIRECT_URI=http://localhost:5173/auth/callback
export SUPPLY_RESPONSE_ALEX_OBJECT_ID=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa
export SUPPLY_RESPONSE_JORDAN_OBJECT_ID=bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb
export SUPPLY_RESPONSE_TAYLOR_OBJECT_ID=cccccccc-cccc-4ccc-8ccc-cccccccccccc

./infra/entra/configure.sh --dry-run --fixture tests/auth/fixtures/configure.json
./infra/entra/assign-personas.sh --dry-run --fixture tests/auth/fixtures/assignments.json
```

These are synthetic fixture UUIDs, not deployment values.

## Approval-gated tenant work

Do not perform these steps without explicit approval for the target directory:

1. Confirm the active Azure CLI directory is the verified `willmacdonald.com` directory. Record its immutable tenant UUID in `SUPPLY_RESPONSE_EXPECTED_TENANT_ID`, the Work IQ resource application UUID in `SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID`, and the exact registered SPA redirect URI in `SUPPLY_RESPONSE_REDIRECT_URI`.
2. Set `SUPPLY_RESPONSE_CONFIRM_TENANT=willmacdonald.com`, then run `./infra/entra/configure.sh --apply`. It creates or patches the two applications and service principals, resolves the single enabled `WorkIQAgent.Ask` scope by exact value, and writes deployment IDs to ignored `infra/entra/.env.tenant` with mode `0600`.
3. Review and grant tenant consent for the API's delegated `WorkIQAgent.Ask` permission and the Web application's delegated `access_as_user` permission. Consent is deliberately not automated by `configure.sh`.
4. Resolve Alex, Jordan, and Taylor to immutable Entra **object IDs** through an approved administrative process. Never configure persona authorization by UPN or display name. Export the three `SUPPLY_RESPONSE_*_OBJECT_ID` values and run `./infra/entra/assign-personas.sh --apply`.
5. After propagation, separately approve the read-only live validations `./infra/entra/configure.sh --check` and `./infra/entra/assign-personas.sh --check`.

The assignment is exact and fixed:

| Stable persona | Deployment binding | API app roles |
|---|---|---|
| `RL-PERSONA-ALEX` | `SUPPLY_RESPONSE_ALEX_OBJECT_ID` | `material_planner`, `response_approver` |
| `RL-PERSONA-JORDAN` | `SUPPLY_RESPONSE_JORDAN_OBJECT_ID` | `quality_approver` |
| `RL-PERSONA-TAYLOR` | `SUPPLY_RESPONSE_TAYLOR_OBJECT_ID` | `finance_approver` |

The scripts reject missing, malformed, duplicate, disabled, or ambiguous tenants, scopes, roles, IDs, and assignments. Re-running apply is idempotent: registrations are updated by client ID and existing exact role assignments are left in place.

## Runtime configuration

The SPA's four settings are all-or-nothing:

```text
VITE_ENTRA_TENANT_ID=<tenant UUID>
VITE_ENTRA_WEB_CLIENT_ID=<Web application client UUID>
VITE_ENTRA_API_SCOPE=api://<API application client UUID>/access_as_user
VITE_ENTRA_REDIRECT_URI=<exact registered redirect URI>
```

MSAL uses the tenant-specific authority, redirect flow, silent acquisition, and `sessionStorage`; it never uses `localStorage`. The API client asks MSAL for a token for each request and attaches it only in the `Authorization: Bearer` header. Fallback mode remains usable when all four variables are absent.

The backend `AuthService` accepts only RS256 access tokens from the exact tenant issuer and API audience. It validates signature, expiry, not-before time, `tid`, `oid`, app roles, exact persona bindings, and bounded Entra metadata/JWKS. It preserves the inbound token only inside a redacted, non-serializable user assertion for a later Work IQ on-behalf-of exchange. Decision identity snapshots retain tenant ID, object ID, stable persona ID, UPN/display name, and effective roles—but never the bearer token.

Live FastAPI dependency composition and route enforcement remain isolated for Task 17 so fallback browser tests and the existing local composition are not changed prematurely. OBO token exchange also needs a securely managed confidential-client credential; API access-token validation itself does not. No secret or certificate is generated by these scripts or stored in this repository.

## Official references

- [Microsoft identity platform access-token claims](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference)
- [Secure applications and APIs by validating claims](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation)
- [Application resource and `AzureADMyOrg`](https://learn.microsoft.com/en-us/graph/api/resources/application?view=graph-rest-1.0)
- [Add app roles and receive them in tokens](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps)
- [Grant an app-role assignment](https://learn.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignedto?view=graph-rest-1.0)
- [MSAL.js caching](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/caching)
- [Acquire tokens silently, then redirect when interaction is required](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/acquire-token)
- [OAuth 2.0 on-behalf-of flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)
