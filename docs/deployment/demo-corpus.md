# Work IQ Demo Corpus runbook

This runbook creates only the purpose-built, fictional Microsoft 365 artifacts used by the live RL-001 demonstration. The application never creates or sends these artifacts. Do not use real supplier, customer, or employee data.

## One-time tenant setup

1. Create an unlicensed shared mailbox with display name `RL-Supplier Alpha`. Grant the operator `Send As`, then send the exact text from `data/demo-corpus/supplier-alpha-message.md` to Alex's purpose-built mailbox. Do not commit the mailbox address or sender UPN.
2. Sign in as Jordan and post the exact text from `data/demo-corpus/supplier-beta-quality-message.md` to a Teams channel that Alex can read.
3. Sign in as Alex and open both artifacts. Record only their opaque source IDs as `SUPPLY_RESPONSE_WORKIQ_ALPHA_SOURCE_ID` and `SUPPLY_RESPONSE_WORKIQ_BETA_SOURCE_ID` in the ignored deployment file `infra/entra/.env.tenant`. Set `SUPPLY_RESPONSE_WORKIQ_TENANT_SHAREPOINT_HOST` to the one exact tenant hostname (for example, `contoso.sharepoint.com`, not a wildcard or URL). Never commit UPNs, tenant IDs, source IDs, bearer assertions, browser storage state, or client credentials.
4. Confirm both artifacts visibly contain `DEMO CORPUS — FICTIONAL` and contain no real supplier or customer information.
5. Leave the artifacts in place across rehearsals. Source age does not require regeneration: business validity is evaluated against the case's Scenario Effective Time and the explicit effective/expiry facts, not the current calendar date.

## Work IQ prerequisites

Work IQ API access currently uses usage-based billing through Copilot Credits. A Microsoft 365 Copilot license is not required for this API. Before live verification:

- enable Work IQ in the tenant;
- establish the usage-based billing plan and assign Alex to it;
- provision the Work IQ service principal;
- grant administrator consent for the delegated `WorkIQAgent.Ask` permission;
- bind the API confidential-client credential outside the repository; and
- verify a delegated A2A request while signed in as Alex.

Application-only authentication is forbidden. Taylor and Jordan must not be used for the canonical Work IQ retrieval.

## Live-test preparation

Immediately before the live test, acquire a fresh Alex API access token interactively and write it to a local file outside the repository with owner-only permissions. Also create a Playwright storage-state file from an interactive Alex browser sign-in, keep it outside the repository with owner-only permissions, and set `SUPPLY_RESPONSE_WORKIQ_ALEX_STORAGE_STATE_FILE` to its path. Set the complete live-test environment described in `tests/integration/test_workiq_live.py`, including Alex's exact Entra object ID, the assertion-file path, both opaque source IDs, the exact tenant SharePoint hostname, and the storage-state path. The test runs the same `AuthService` signature/issuer/audience/lifetime/tenant/object/role/scope checks as the API before OBO, rejects an assertion file older than ten minutes, and refuses partial configuration before importing MSAL or making a network request.

The local contract suite uses only fictional captured-style fixtures. It does not fetch citation URLs. Live verification retrieves both artifacts, requires authoritative normalized evidence with current retrieval timestamps, and opens every returned citation in Alex's authenticated browser context. Every redirect hop and final URL must remain on the exact approved Microsoft 365 destination hosts, and the final artifact view must return a 2xx response; login redirects, broken responses, and off-host navigation fail the gate.
