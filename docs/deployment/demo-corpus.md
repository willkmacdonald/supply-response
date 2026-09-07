# Work IQ Demo Corpus runbook

This runbook creates only the purpose-built, fictional Microsoft 365 artifacts used by the live RL-001 demonstration. The application never creates or sends these artifacts. Do not use real supplier, customer, or employee data.

## One-time tenant setup

1. Create an unlicensed shared mailbox with display name `RL-Supplier Alpha`. Grant the operator `Send As`, then send the exact text from `data/demo-corpus/supplier-alpha-message.md` to Alex's purpose-built mailbox. Do not commit the mailbox address or sender UPN.
2. Sign in as Jordan and post the exact text from `data/demo-corpus/supplier-beta-quality-message.md` to a Teams channel that Alex can read.
3. Record the supplier and Quality message IDs plus the supplier sender, Jordan's immutable Entra object ID, and the exact Team/channel IDs in the ignored deployment environment. These values validate independently discovered results; they are never included in discovery prompts and never serve as direct-fetch fallbacks. Set `SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST` to the one exact tenant hostname (for example, `contoso.sharepoint.com`, not a wildcard or URL). Never commit tenant-specific bindings, bearer assertions, browser storage state, or client credentials.
4. Confirm both artifacts visibly contain `DEMO CORPUS — FICTIONAL` and contain no real supplier or customer information.
5. Leave the artifacts in place across rehearsals. Source age does not require regeneration: business validity is evaluated against the case's Scenario Effective Time and the explicit effective/expiry facts, not the current calendar date.

## Work IQ prerequisites

Work IQ API access currently uses usage-based billing through Copilot Credits. A Microsoft 365 Copilot license is not required for this API. Before live verification:

- enable Work IQ in the tenant;
- establish the usage-based billing plan and assign Alex to it;
- provision the Work IQ service principal;
- grant administrator consent for the delegated `WorkIQAgent.Ask` permission;
- bind the API confidential-client credential outside the repository; and
- verify the normal application MCP path while signed in as Alex.

Application-only authentication is forbidden. Taylor and Jordan must not be used for the canonical Work IQ retrieval.

## Live-test preparation

The local contract suite uses only fictional captured-style fixtures and fake Entra/MCP HTTP. It proves that a normally signed Alex request discovers and fetches both sources without calling Graph directly, but it is not live tenant acceptance. The older `tests/integration/test_workiq_live.py` gate covers only the retained legacy A2A adapter and must not be cited as proof of the deployed MCP path.

For live acceptance, use the deployed browser's normal **Analyze disruption** action while signed in as Alex. Require both sources to be independently discovered, fetched, validated, accepted by the evidence policy, and rendered with their navigable citations; one source or a link-only response is failure. Every citation redirect and final URL must remain on the exact approved Microsoft 365 destination hosts. Retain only sanitized stage, lineage, revision and acceptance evidence—never tokens, discovery answers, raw response bodies, or source text outside the existing evidence model.
