# Reporting release setting implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. The user approved the coordinated release; this narrow task repairs its missing configuration path before any cloud publication.

**Goal:** Carry the optional reporting acceptance receipt through the existing shell/Bicep deployment without activating it automatically.

**Architecture:** Preserve the existing app receipt verifier and generated artifact digest. Pass one optional, default-empty string from the deploy script through AZD parameters and the runtime settings object to the Container App. Missing/empty means inactive, including deliberate removal of a previously configured receipt.

**Tech Stack:** Bash 3.2, Bicep, JSON, pytest and the existing Bicep compiler.

## Global Constraints

- No publication, authentication, credential handling, cloud calls, new resources, roles, scaling changes, receipt issuance, merge or push in this implementation task.
- Preserve `SUPPLY_RESPONSE_POWER_BI_DEPLOYMENT_RECEIPT` independently from `SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT`.
- Do not compute an acceptance receipt from local tests or deployment success.
- Blank or absent reporting receipt must not activate `saved-analysis-v1`.
- Explicitly clearing the setting must not reuse an old AZD value.
- Preserve bootstrap and existing deployment safety gates and unchanged artifact digest.

### Task 1: End-to-end optional receipt configuration

**Files:** `scripts/deploy_personal_tenant.sh`, `infra/main.bicep`, `infra/main.parameters.json`, `infra/modules/container-apps.bicep`, `tests/deployment/test_infrastructure.py`, `docs/deployment/personal-tenant.md`.

**Interfaces:** Existing `Settings.power_bi_reporting_receipt` and verifier require no change. The script already writes required settings before provisioning; add a separate optional assignment after that loop. Main Bicep passes `runtimeSettings` to the Container App module.

- [x] Add a failing wiring regression in the existing test file, using `_read` and JSON parsing:

```python
def test_reporting_receipt_has_optional_declarative_wiring():
    main = _read("infra/main.bicep")
    params = json.loads(_read("infra/main.parameters.json"))["parameters"]
    module = _read("infra/modules/container-apps.bicep")
    script = _read("scripts/deploy_personal_tenant.sh")
    assert "param powerBiReportingReceipt string = ''" in main
    assert "powerBiReportingReceipt: powerBiReportingReceipt" in main
    assert params["powerBiReportingReceipt"]["value"] == "${SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT}"
    assert "{ name: 'SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT', value: runtimeSettings.powerBiReportingReceipt }" in module
    assert '"${SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT:-}"' in script
    required = script.split("required_runtime_settings=(", 1)[1].split(")", 1)[0]
    assert "SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT" not in required
```

- [x] Run that test and record the missing-wiring failure before implementation.
- [x] Add the default-empty Bicep parameter after `powerBiDeploymentReceipt`, pass it in `runtimeSettings`, add its matching JSON parameter, and add the Container App environment entry shown above after the legacy receipt.
- [x] After the existing required-setting loop, add exactly one explicit optional update (both absent and empty clear a previously saved AZD receipt):

```bash
# Acceptance is external to deployment; blank explicitly deactivates new links.
safe_run azd-setting-SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT azd env set SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT "${SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT:-}"
```

- [x] Add a parameterized executable shell regression for absent, empty and a supplied 64-character fixture value. Extract this single `safe_run azd-setting-SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT` line from the actual script, execute it under Bash with a fake `safe_run` that verifies command argv are exactly `azd env set SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT <expected>`, and assert success. The fake must compare the final argument including empty, not just count invocations. Start with `env` minus the real receipt and use only synthetic values. No Azure CLI execution.
- [x] Document that the operator must supply this setting only after artifact-bound SQL/model/DAX/native/access acceptance. Omission or an explicit empty value disables links on the next declarative deployment. This task neither issues nor installs a receipt.
- [x] Run `.venv/bin/pytest tests/deployment/test_infrastructure.py tests/test_reporting_activation.py -o addopts='' -q` once, covering actual Bicep compilation and existing API negative/positive gates. Run `bash -n scripts/deploy_personal_tenant.sh`, changed-file Ruff, and `git diff --check`. Report dependency-access failures separately if any.
- [x] Commit only the scoped tracked files; write full RED/GREEN evidence to `.superpowers/sdd/reporting-release-plumbing-report.md`, then hand off for independent review. Do not stage scratch reports.

Task completed in `5ac9ebf`. Independent task review: spec compliant and quality
approved; no Critical/Important findings. One inherited Starlette dependency
deprecation warning remains a maintenance item, not a new functional regression.

## Remaining release gates

This is not live acceptance. Capture existing remote definitions and bindings before replacement; verify the tested source revision and exact target IDs. Apply SQL, then model/report, then app with links inactive. Native and read-only DAX acceptance precede receipt activation. The existing four analyzed cases lack a within-case historical analysis; a bounded fictional fixture needs explicit user authorization. Native browser inspection also needs the user's Mac unlocked. No saved data may be rewritten or operational actions executed to fabricate acceptance.
