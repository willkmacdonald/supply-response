# Foundry Luna Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind all three Supply Response prompt agents to the existing `gpt-5.6-luna` deployment, make publication safe to retry, and promote exact verified agent bindings into the ignored personal-tenant deployment environment.

**Architecture:** The three committed manifests remain the source of truth. Publication first validates the one approved model deployment, then reconciles each manifest against immutable Foundry agent versions using a deterministic contract fingerprint. A separate verifier compares every remote field to the committed contract and emits the deployment receipt consumed by the API runtime.

**Tech Stack:** Python 3.12, Pydantic, pytest, Azure AI Projects SDK, Microsoft Foundry SDK, Azure CLI, Azure Developer CLI (`azd`).

## Global Constraints

- Work directly on `main`, as approved, but use one focused commit per task.
- Preserve the user's unrelated `README.md` and `docs/ROADMAP.md` changes.
- Do not create another Foundry project or model deployment. Reuse project `m365` and deployment `gpt-5.6-luna` in East US 2.
- Do not change Azure or Foundry role assignments.
- Do not invoke agents or run evaluations during publication. Those are separate, cost-incurring approval gates.
- For every `azd` Foundry command, set `AZURE_DEV_USER_AGENT=microsoft_foundry_skill` inline.
- Never commit tenant IDs, Entra object IDs, UPNs, credentials, generated receipts, or `.azure` environment values.
- Before each commit, run the task-specific tests and `git diff --check` on the files being committed.

---

## Task 1: Freeze the prompt-agent contract on Luna

**Files:**

- Modify: `agents/manifests/__init__.py`
- Modify: `agents/manifests/signal.json`
- Modify: `agents/manifests/context.json`
- Modify: `agents/manifests/decision.json`
- Modify: `tests/agents/test_foundry_artifacts.py`

- [ ] **Step 1: Add failing tests for the exact trusted deployment**

Add tests that prove all committed manifests resolve to one exact deployment and that any other model string is rejected:

```python
from pydantic import ValidationError

from agents.manifests import TRUSTED_MODEL_DEPLOYMENT, AgentManifest, load_manifests


def test_committed_manifests_use_only_the_trusted_model(root: Path) -> None:
    manifests = load_manifests(root)
    assert TRUSTED_MODEL_DEPLOYMENT == "gpt-5.6-luna"
    assert {manifest.model for manifest in manifests.values()} == {
        TRUSTED_MODEL_DEPLOYMENT
    }


def test_manifest_rejects_a_different_model(valid_manifest: dict[str, object]) -> None:
    valid_manifest["model"] = "gpt-4.1-mini"
    with pytest.raises(ValidationError, match="gpt-5.6-luna"):
        AgentManifest.model_validate(valid_manifest)
```

Adapt the fixture name to the existing test helpers, without weakening the assertions.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
uv run pytest tests/agents/test_foundry_artifacts.py -q
```

Expected: the new exact-model tests fail because the manifests still reference `gpt-4.1-mini` and the validator accepts arbitrary deployment names.

- [ ] **Step 3: Implement the exact model invariant**

In `agents/manifests/__init__.py`, export one constant and make manifest validation require it:

```python
TRUSTED_MODEL_DEPLOYMENT = "gpt-5.6-luna"
```

Keep the existing non-empty/string validation, but replace the broad regex acceptance with an exact comparison whose error names the trusted deployment. Update the `model` field in all three JSON manifests to `gpt-5.6-luna`. Do not change agent names, descriptions, instruction paths, instructions, or tools.

- [ ] **Step 4: Run focused and repository tests**

Run:

```bash
uv run pytest tests/agents/test_foundry_artifacts.py -q
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Review and commit only Task 1 files**

Run:

```bash
git diff --check -- agents/manifests tests/agents/test_foundry_artifacts.py
git diff -- agents/manifests tests/agents/test_foundry_artifacts.py
git add agents/manifests/__init__.py agents/manifests/signal.json agents/manifests/context.json agents/manifests/decision.json tests/agents/test_foundry_artifacts.py
git commit -m "fix(agents): bind prompt agents to luna"
```

Expected: the commit contains only the manifest contract, three model substitutions, and their tests.

---

## Task 2: Make publication preflighted and retry-safe

**Files:**

- Modify: `scripts/publish_foundry_agents.py`
- Modify: `tests/agents/test_foundry_artifacts.py`

- [ ] **Step 1: Extend the fake Foundry client for reconciliation tests**

Extend the existing fake agents collection so it can:

- return versions from `list_versions(agent_name)`;
- return an empty list when an agent does not exist;
- record calls to `create_version` including metadata;
- simulate failure after one successful creation;
- expose a fake `deployments.get(name)` result with the real data-plane SDK
  shape: `name` and `model_name`, without a provisioning-state field.

Keep this fake local to the test module. It must model only SDK behavior used by the publisher.

- [ ] **Step 2: Add failing publication-contract tests**

Add focused tests for these observable behaviors:

1. Model preflight happens before the first `create_version` call.
2. Missing or mismatched `gpt-5.6-luna` deployment identity fails before any
   agent mutation.
3. First publication creates exactly three versions with metadata keys:
   - `supply_response_contract_sha256`
   - `supply_response_role`
4. Repeating the same publication reuses all three versions and creates none.
5. A simulated failure after the first creation can be retried; the retry reuses the first version and creates only the remaining two.
6. One matching fingerprint with remote field drift fails rather than reusing it.
7. More than one version carrying the same fingerprint fails as ambiguous.

Also assert output is emitted after each successful reconciliation so a partial run preserves the exact `name=version` already created.

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
uv run pytest tests/agents/test_foundry_artifacts.py -q
```

Expected: reconciliation and model-preflight tests fail against the current always-create publisher.

- [ ] **Step 4: Add deterministic contract fingerprinting**

In `scripts/publish_foundry_agents.py`, compute SHA-256 over canonical JSON containing exactly:

```python
{
    "agent_name": manifest.agent_name,
    "description": manifest.description,
    "instructions_sha256": manifest.instructions_sha256,
    "model": manifest.model,
    "role": manifest.role,
    "tools": [],
}
```

Serialize with sorted keys and compact separators before hashing. Use the digest in metadata:

```python
metadata = {
    "supply_response_contract_sha256": fingerprint,
    "supply_response_role": manifest.role,
}
```

The fingerprint excludes tenant and version data so identical committed contracts reconcile consistently across deployments.

- [ ] **Step 5: Preflight the exact Luna data-plane identity before mutation**

Call:

```python
deployment = project.deployments.get(TRUSTED_MODEL_DEPLOYMENT)
```

Require the exact deployment name/model binding. Raise a descriptive error
before processing any manifest when it is missing or points to a different
model. Do not inspect a nonexistent provisioning-state attribute: the live
`azure-ai-projects` `ModelDeployment` contract exposes identity and model
metadata, but not Azure Resource Manager provisioning state. Do not create or
update a model deployment.

- [ ] **Step 6: Reconcile immutable agent versions**

For each role in the existing deterministic order:

1. Call `project.agents.list_versions(agent_name)`.
2. Treat only `azure.core.exceptions.ResourceNotFoundError` as no existing versions; propagate authorization, network, throttling, and other SDK errors.
3. Filter versions whose metadata fingerprint equals the local fingerprint.
4. If none match, call `create_version(...)` with the manifest contract and metadata.
5. If exactly one matches, compare its name, description, model, instructions, tools, role metadata, and fingerprint to the manifest; reuse only an exact match.
6. If multiple versions match, fail with an ambiguity error that identifies the agent and matching versions.
7. Emit `agent_name=version` immediately after each role is created or safely reused.

Do not delete or mutate old immutable versions.

- [ ] **Step 7: Run focused and repository tests**

Run:

```bash
uv run pytest tests/agents/test_foundry_artifacts.py -q
uv run pytest -q
```

Expected: all tests pass, including the partial-failure retry case.

- [ ] **Step 8: Review and commit only Task 2 files**

Run:

```bash
git diff --check -- scripts/publish_foundry_agents.py tests/agents/test_foundry_artifacts.py
git diff -- scripts/publish_foundry_agents.py tests/agents/test_foundry_artifacts.py
git add scripts/publish_foundry_agents.py tests/agents/test_foundry_artifacts.py
git commit -m "fix(agents): reconcile Foundry publications"
```

---

## Task 3: Verify canonical bindings and emit the runtime receipt

**Files:**

- Modify: `scripts/verify_foundry_agents.py`
- Modify: `tests/agents/test_foundry_artifacts.py`
- Modify: `tests/agents/test_foundry_live.py`
- Modify: `docs/deployment/personal-tenant.md`

- [ ] **Step 1: Add failing tests for canonical environment names**

Change verifier/live-test fixtures to use only the canonical runtime variables:

```text
SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_VERSION
```

Add a test proving the legacy variables without `_AGENT_` are not accepted.

- [ ] **Step 2: Add failing receipt tests**

Add a pure helper test for a deterministic receipt over this exact newline-delimited order:

```text
<project-endpoint>
<signal-agent-name>
<signal-agent-version>
<context-agent-name>
<context-agent-version>
<decision-agent-name>
<decision-agent-version>
```

Assert the live verifier emits the receipt only after all three remote versions pass exact contract verification:

```text
SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT=<64 lowercase hexadecimal characters>
```

Add a failure test proving no receipt is emitted when any remote field drifts.

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```bash
uv run pytest tests/agents/test_foundry_artifacts.py tests/agents/test_foundry_live.py -q
```

Expected: canonical binding and receipt tests fail with the current verifier.

- [ ] **Step 4: Fix binding lookup and centralize receipt generation**

In `scripts/verify_foundry_agents.py`:

- read the canonical `_AGENT_NAME` and `_AGENT_VERSION` variables;
- retain exact remote checks for name, version, description, model, instructions, and tools;
- add a pure `deployment_receipt(project_endpoint, versions)` helper using UTF-8 SHA-256 and the fixed signal/context/decision order;
- print checked versions first;
- print the receipt assignment only after all checks succeed.

Do not accept UPNs, display names, mutable labels, or unordered mappings as receipt inputs.

- [ ] **Step 5: Update the personal-tenant runbook**

Replace the manual inline Python hashing recipe in `docs/deployment/personal-tenant.md` with the verifier command and its emitted receipt. Document that operators copy the exact emitted assignment into the ignored azd environment; do not put a real receipt in the runbook.

- [ ] **Step 6: Run focused and repository tests**

Run:

```bash
uv run pytest tests/agents/test_foundry_artifacts.py tests/agents/test_foundry_live.py -q
uv run pytest -q
```

The live invocation test must remain skipped unless its explicit live-test gate is set. Expected: all ordinary tests pass without invoking an agent.

- [ ] **Step 7: Review and commit only Task 3 files**

Run:

```bash
git diff --check -- scripts/verify_foundry_agents.py tests/agents/test_foundry_artifacts.py tests/agents/test_foundry_live.py docs/deployment/personal-tenant.md
git diff -- scripts/verify_foundry_agents.py tests/agents/test_foundry_artifacts.py tests/agents/test_foundry_live.py docs/deployment/personal-tenant.md
git add scripts/verify_foundry_agents.py tests/agents/test_foundry_artifacts.py tests/agents/test_foundry_live.py docs/deployment/personal-tenant.md
git commit -m "fix(agents): verify canonical Foundry bindings"
```

---

## Task 4: Publish, verify, and promote the three immutable versions

**Files:**

- Modify: `.azure/deployment-plan.md`
- Create ignored artifact: `.artifacts/deployment/foundry-receipt.txt`
- Modify ignored environment: `.azure/supply-response-personal/.env`

- [ ] **Step 1: Establish a clean implementation checkpoint**

Run:

```bash
git status --short
uv run pytest -q
git log -3 --oneline
```

Expected: tests pass and the last three focused commits are present. `README.md`, `docs/ROADMAP.md`, and the pre-existing `.azure/deployment-plan.md` edits may still appear; do not stage the first two.

- [ ] **Step 2: Reconfirm the exact target and read-only prerequisites**

Run read-only checks:

```bash
az account show --query '{tenant:tenantId,subscription:id,name:name}' -o json
az resource show --resource-group DefaultResourceGroup-NCUS --name m365-resource --resource-type Microsoft.CognitiveServices/accounts --query '{id:id,location:location,kind:kind}' -o json
```

Then use the repository's existing Foundry inspection command or SDK check to verify:

- project endpoint is `https://m365-resource.services.ai.azure.com/api/projects/m365`;
- region is East US 2;
- the Foundry data-plane SDK returns deployment name and model name exactly
  `gpt-5.6-luna`;
- an Azure Resource Manager read of the exact deployment reports provisioning
  state `Succeeded` immediately before publication;
- current identity can read deployments and agent versions.

Also confirm the endpoint and immutable project resource ID still equal the
values already promoted to the ignored `supply-response-personal` environment.
They are retained bindings, not new outputs from agent publication.

Stop before mutation if tenant, subscription, project, region, model deployment, or permissions differ.

- [ ] **Step 3: Load ignored deployment bindings without printing secrets**

Use `azd env get-values --environment supply-response-personal` to export the already-promoted project endpoint and tenant ID into the current shell. Do not echo the full environment or write these values into tracked files.

- [ ] **Step 4: Publish or reconcile the three agents**

With the inline Foundry user-agent marker required by the skill, run:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill uv run python scripts/publish_foundry_agents.py --publish
```

Expected: exactly three immediate output lines, one each for signal, context, and decision, in the form `agent-name=immutable-version`. A retry after interruption must reuse any already-matching versions.

Capture the exact names and versions in shell variables for verification. Do not infer or renumber versions.

- [ ] **Step 5: Verify the remote contracts and derive the receipt**

Set the six canonical agent name/version variables from Step 4 and run:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill uv run python scripts/verify_foundry_agents.py --live
```

Expected: three verified binding lines followed by one exact `SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT=<sha256>` line. Stop if any manifest/remote comparison fails.

- [ ] **Step 6: Promote the seven verified values to the ignored azd environment**

Set only these values in `supply-response-personal`:

```text
SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT
```

Use `azd env set --environment supply-response-personal KEY VALUE` for each exact verified value. Do not promote provisional output from a failed verifier.

- [ ] **Step 7: Write a local operator receipt**

Create `.artifacts/deployment/foundry-receipt.txt` containing:

- UTC verification timestamp;
- project endpoint;
- immutable project resource ID;
- three exact agent name/version pairs;
- deployment receipt;
- commit SHA containing Tasks 1–3.

Set file permissions to `0600`, confirm the path is ignored with `git check-ignore`, and never stage it.

- [ ] **Step 8: Re-run read-only deployment preview**

Run the repository's existing personal-tenant preview command with:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill
```

Expected: the seven Foundry agent/receipt inputs are no longer missing. Given the current baseline of 17 missing inputs, the preview should report 10 remaining inputs, all outside this task's Foundry publication scope. Investigate rather than editing contracts if the count differs.

- [ ] **Step 9: Record evidence in the deployment plan**

Update `.azure/deployment-plan.md` with:

- Luna deployment preflight result;
- whether each agent was created or reused;
- exact immutable version bindings;
- verifier success and receipt fingerprint;
- preview count before and after;
- explicit statement that no invocation or evaluation was performed.

Do not include tenant secrets, credentials, tokens, or UPNs.

- [ ] **Step 10: Verify and commit only tracked deployment evidence**

Run:

```bash
git diff --check -- .azure/deployment-plan.md
git status --short
git check-ignore .artifacts/deployment/foundry-receipt.txt
git add .azure/deployment-plan.md
git commit -m "docs: record Foundry Luna publication"
```

Expected: the ignored environment and local receipt are absent from the commit; unrelated `README.md` and `docs/ROADMAP.md` changes remain untouched.

- [ ] **Step 11: Stop at the cost boundary**

Report publication and exact verification results, then ask the user to choose one next action:

1. Run one bounded live invocation test.
2. Run the approved evaluation workflow from the agent instructions.
3. Stop and defer invocation/evaluation.

Do not perform options 1 or 2 without fresh explicit approval.

---

## Final Verification

- [ ] Run the complete non-live suite:

```bash
uv run pytest -q
```

- [ ] Confirm tracked-file hygiene:

```bash
git diff --check
git status --short
git log -4 --oneline
```

- [ ] Confirm the three manifests all name `gpt-5.6-luna`, the live verifier used canonical `_AGENT_` variables, and the ignored receipt matches the seven promoted bindings.
- [ ] Confirm no model/project deployment, RBAC mutation, agent invocation, or evaluation occurred outside the approved scope.
