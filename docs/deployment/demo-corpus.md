# Work IQ Demo Corpus runbook

This runbook creates only the purpose-built, fictional Microsoft 365 artifacts used by the live RL-001 demonstration. The application never creates or sends these artifacts. Do not use real supplier, customer, or employee data.

## One-time tenant setup

1. Create an unlicensed shared mailbox with display name `RL-Supplier Alpha`. Grant the operator `Send As`, then send the exact text from `data/demo-corpus/supplier-alpha-message.md` to Alex's purpose-built mailbox. Do not commit the mailbox address or sender UPN.
2. Sign in as Jordan and post the exact text from `data/demo-corpus/supplier-beta-quality-message.md` to a Teams channel that Alex can read.
3. Sign in as Alex and open both artifacts. Record only their opaque source IDs as `SUPPLY_RESPONSE_WORKIQ_ALPHA_SOURCE_ID` and `SUPPLY_RESPONSE_WORKIQ_BETA_SOURCE_ID` in the ignored deployment file `infra/entra/.env.tenant`. Never commit UPNs, tenant IDs, source IDs, bearer assertions, or client credentials.
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

Immediately before the live test, acquire a fresh Alex API access token interactively and write it to a local file outside the repository with owner-only permissions. Set the complete live-test environment described in `tests/integration/test_workiq_live.py`, including the assertion-file path and both opaque source IDs. The test rejects an assertion file older than ten minutes and refuses partial configuration before importing MSAL or making a network request.

The local contract suite uses only fictional captured-style fixtures. It does not fetch citation URLs. Live verification retrieves both artifacts, requires authoritative normalized evidence with current retrieval timestamps, and performs a bounded navigation check for every returned Microsoft 365 citation.
