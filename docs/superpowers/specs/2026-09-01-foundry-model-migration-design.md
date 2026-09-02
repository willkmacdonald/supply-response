# Foundry Agent Model Migration Design

**Status:** Approved

**Date:** 2026-09-01

## Context

The three Supply Response prompt-agent manifests name `gpt-4.1-mini`. During
personal-tenant publication preflight, the selected East US 2 Foundry project
`m365-resource/m365` had no deployment by that name. The project already had a
successful `gpt-5.6-luna` Global Standard deployment.

Microsoft currently classifies `gpt-4.1-mini` version `2025-04-14` as Legacy,
with retirement scheduled for 2027-04-14. Microsoft classifies
`gpt-5.6-luna` version `2026-07-09` as GA, with retirement scheduled for
2028-01-11. Reusing the existing deployment also avoids adding another model
deployment and consuming additional allocated quota solely for this demo.

## Decision

All three versioned prompt-agent manifests will bind to the existing deployment
name `gpt-5.6-luna`:

- `supply-response-signal`
- `supply-response-context`
- `supply-response-decision`

The model deployment name remains part of each committed manifest rather than a
runtime override. This preserves an auditable, testable publication contract.

No other agent behavior changes. Agent names, instructions, descriptions, and
empty tool arrays remain fixed. Work IQ retrieves tenant evidence before model
invocation. Deterministic application services retain exclusive authority for
arithmetic, feasibility, approvals, ranking, Decision creation, and execution.

## Alternatives Rejected

### Deploy `gpt-4.1-mini`

Rejected because it would add a new deployment for a Legacy model while the
selected project already contains a suitable GA deployment.

### Runtime model override

Rejected because an environment-selected model could diverge from the reviewed
manifest without a source-controlled change or corresponding contract test.

### Use different models for different agents

Rejected because the three agents have small, bounded extraction or explanation
roles. Per-agent model selection would add deployment and validation complexity
without serving an approved requirement.

## Publication and Verification Contract

Implementation will:

1. Change the three manifest model values to exactly `gpt-5.6-luna`.
2. Update contract tests to reject any other model deployment name.
3. Run the local manifest and Foundry artifact tests before publication.
4. Publish exactly one new immutable version of each agent into the selected
   `m365-resource/m365` project.
5. Verify each published name, version, model, instruction hash, and empty-tool
   contract against its committed manifest.
6. Store only the resulting agent names, versions, endpoint, immutable project
   resource ID, and deterministic deployment receipt in the ignored azd
   environment. No token, credential, or prompt payload enters deployment state.

Remote invocation and evaluation are separate cost-incurring gates. Publication
does not authorize either. If publication fails partway, completed immutable
versions remain visible for audit; the retry must first inspect them and must not
silently publish duplicate versions.

## Acceptance Impact

The frozen business and demo acceptance criteria are unchanged. Live acceptance
still requires Foundry Agent Service and Microsoft Agent Framework orchestration,
while deterministic services retain authority. The only revised deployment
contract is the trusted model name used by the three prompt-agent versions.

## Sources

- Microsoft Foundry model retirement schedule:
  <https://learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule>
- Tenant read-only model-deployment and quota inspection performed 2026-09-01.
