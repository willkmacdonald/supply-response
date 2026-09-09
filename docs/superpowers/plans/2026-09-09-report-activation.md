# Saved-analysis reporting activation implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this narrow task after controller review. Do not spawn workers or issue a deployment receipt as part of this plan.

**Goal:** Advertise `power_bi_reporting_contract=saved-analysis-v1` only when a separately configured release attestation matches this API build's generated reporting artifacts and the composed report/database bindings.

**Architecture:** Keep all existing readiness semantics. A new optional receipt is checked when `/api/runtime` constructs its deployment contract, after existing live/Power BI readiness checks. A generated Python constant packaged inside `apps` binds the API to complete local report/model artifacts and SQL; runtime never reads the unshipped `fabric` tree.

**Tech Stack:** Python standard library, existing Pydantic settings, pytest and FastAPI TestClient. No dependencies, live calls, deployment, environment updates or SQL schema changes.

## Execution checkpoint

Implemented and independently reviewed through `7549c3f`. The controller reran
60 activation/API compatibility tests and the exact generated-digest check;
all passed. The generator now emits formatter-stable Python, preserving exact
artifact equality through normal commit hooks. One inherited TestClient warning
remains. A regression distinguishing raw and composed report URLs is assigned to
the final Stage 5 digest refresh; production already uses the composed URL.

No receipt was issued or installed. The digest must be regenerated after the
traditional walkthrough changes, and live DAX/render/access acceptance remains
separate from these local checks.

## Preconditions and exact scope

Implement only after the generator and artifact integration tasks are complete and verified. At design time `fabric/report_pages.py` and `fabric/report_model.py` do not yet exist; their reviewed APIs are `verify(Path)` and `verify(Path, Path)` respectively. The generated report must already contain all eight pages and the semantic model all five tables.

Create `fabric/report_contract.py`, `apps/api/app/_reporting_artifact.py`, and `tests/test_reporting_activation.py`. Modify only `apps/api/app/settings.py`, `apps/api/app/readiness.py`, and `apps/api/app/routes/health.py`. No changes to `dependencies.py`, `ReadinessSnapshot`, `FabricBoundReadiness`, `RuntimeResponse`, frontend navigation, Dockerfile, infrastructure or existing receipt issuance. Dockerfile already has `COPY apps ./apps`; the wheel packages `apps`. Thus both distribution paths include the Python constant and need no `fabric` runtime import.

The optional setting is `SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT`. Leave it absent everywhere. Existing `SUPPLY_RESPONSE_POWER_BI_DEPLOYMENT_RECEIPT` retains its URL-only readiness behavior and cannot satisfy the new field. An absent or invalid new receipt omits the contract key entirely, preserving exact legacy JSON tests. The previous `power_bi_available` behavior is unchanged; new frontend links require both it and the new contract.

The new receipt is an operator attestation, not a signature or proof of current availability. Anyone who can set trusted application settings can calculate it; this is the existing deployment trust boundary. It must never be generated automatically merely because local tests or publication pass. Retain old naming for compatibility without adding a misleading new readiness state.

## Task 1: Write failure tests, then implement the gate

- [x] Create `tests/test_reporting_activation.py` with the complete code below. Initially run the legacy-receipt and absent-receipt tests after introducing just the optional Settings field and test imports as needed; the positive activation case must fail because the response lacks the new contract. For the artifact test, first record its expected failure because the compiled artifact module/checker is absent. Do not treat an unrelated import or fixture error as the gate's behavioral RED.

```python
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app.dependencies import build_composition
from apps.api.app.main import create_app
from apps.api.app.readiness import ReadinessSnapshot
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.persistence.sqlite import sqlite_store

ROOT = Path(__file__).resolve().parents[1]
URL = (
    "https://app.powerbi.com/groups/11111111-1111-1111-1111-111111111111"
    "/reports/22222222-2222-2222-2222-222222222222"
)
SERVER = "example.fabric.microsoft.com"
DATABASE = "supply-response"
CONTRACT = "saved-analysis-v1"
KEY = "power_bi_reporting_contract"


def receipt_for(*, url=URL, server=SERVER, database=DATABASE, digest=None,
                contract=CONTRACT):
    # Independent protocol encoder: never call the production verifier to mint tests.
    from apps.api.app._reporting_artifact import REPORTING_ARTIFACT_SHA256

    payload = [
        "supply-response-reporting-receipt-v1", contract,
        REPORTING_ARTIFACT_SHA256 if digest is None else digest,
        url, server, database,
    ]
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def runtime_payload(tmp_path, *, receipt=None, url=URL, server=SERVER,
                    database=DATABASE, verified=True, health="ready",
                    mode=RuntimeMode.LIVE):
    settings = Settings(
        runtime_mode=mode,
        database_url=f"sqlite:///{tmp_path / 'runtime.db'}",
        credential_mode="managed_identity",
        fabric_sql_server=server,
        fabric_sql_database=database,
        power_bi_report_url=url,
        power_bi_reporting_receipt=receipt,
    )

    class Readiness:
        def check(self):
            return ReadinessSnapshot(
                capability_health={"power_bi": health},
                power_bi_verified=verified,
            )

    if mode is RuntimeMode.LIVE:
        services = build_composition(settings, live_components={
            "store": sqlite_store(settings.database_url, runtime_mode=mode),
            "analysis_service": object(), "auth_service": object(),
            "power_bi_url": url, "readiness": Readiness(),
        })
    else:
        services = build_composition(settings)
        # Even an erroneously injected positive readiness cannot enable fallback.
        services.readiness = Readiness()
        services.power_bi_url = url
    with TestClient(create_app(services=services)) as client:
        response = client.get("/api/runtime")
        assert response.status_code == 200
        return response.json()


def test_exact_release_attestation_exposes_contract(tmp_path):
    payload = runtime_payload(tmp_path, receipt=receipt_for())
    assert payload["power_bi_available"] is True
    assert payload["deployment_contract"][KEY] == CONTRACT


@pytest.mark.parametrize("receipt", [None, "", "garbage", "0" * 64])
def test_absent_or_invalid_receipt_keeps_old_readiness_without_new_links(tmp_path, receipt):
    payload = runtime_payload(tmp_path, receipt=receipt)
    assert payload["power_bi_available"] is True
    assert KEY not in payload["deployment_contract"]


def test_legacy_url_receipt_does_not_attest_saved_reporting(tmp_path):
    old = hashlib.sha256(URL.encode()).hexdigest()
    payload = runtime_payload(tmp_path, receipt=old)
    assert payload["power_bi_available"] is True
    assert KEY not in payload["deployment_contract"]


@pytest.mark.parametrize("change", [
    {"digest": "0" * 64}, {"contract": "saved-analysis-v0"},
    {"url": URL.replace("22222222", "33333333")},
    {"server": "other.fabric.microsoft.com"}, {"database": "other"},
])
def test_receipt_must_match_every_release_binding(tmp_path, change):
    payload = runtime_payload(tmp_path, receipt=receipt_for(**change))
    assert KEY not in payload["deployment_contract"]


@pytest.mark.parametrize("url", [
    URL + "/", URL + "/command-center", URL + "?filter=x", URL + "#page",
    URL.replace("https://", "http://"), URL.replace("app.powerbi.com", "example.com"),
    URL.replace("app.powerbi.com", "app.powerbi.com:443"),
    URL.replace("app.powerbi.com", "user@app.powerbi.com"),
    URL.replace("app.powerbi.com", "APP.POWERBI.COM"),
    "https://app.powerbi.com/groups/demo/reports/report", " " + URL,
    URL + "\n", URL.replace("/groups/", "/groups/%31"),
])
def test_even_matching_receipt_cannot_activate_invalid_report_url(tmp_path, url):
    payload = runtime_payload(tmp_path, url=url, receipt=receipt_for(url=url))
    assert KEY not in payload["deployment_contract"]


@pytest.mark.parametrize("change", [
    {"verified": False}, {"health": "unverified"}, {"health": "unavailable"},
])
def test_attestation_does_not_replace_existing_readiness(tmp_path, change):
    payload = runtime_payload(tmp_path, receipt=receipt_for(), **change)
    assert payload["power_bi_available"] is False
    assert KEY not in payload["deployment_contract"]


def test_fallback_cannot_expose_reporting_contract(tmp_path):
    payload = runtime_payload(tmp_path, receipt=receipt_for(), mode=RuntimeMode.FALLBACK)
    assert payload["deployment_contract"] is None
    assert payload["power_bi_available"] is False


def test_reporting_receipt_setting_is_optional_and_environment_backed(monkeypatch):
    monkeypatch.delenv("SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT", raising=False)
    args = {"runtime_mode": RuntimeMode.FALLBACK, "database_url": "sqlite://"}
    assert Settings(**args).power_bi_reporting_receipt is None
    monkeypatch.setenv("SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT", "test-receipt")
    assert Settings(**args).power_bi_reporting_receipt == "test-receipt"


def test_packaged_digest_matches_verified_generated_report_model_and_sql():
    from apps.api.app._reporting_artifact import REPORTING_ARTIFACT_SHA256
    from fabric.report_contract import artifact_digest, generated_module

    assert artifact_digest(ROOT) == REPORTING_ARTIFACT_SHA256
    target = ROOT / "apps/api/app/_reporting_artifact.py"
    assert target.read_text(encoding="utf-8") == generated_module(ROOT)


@pytest.mark.parametrize("relative", [
    "fabric/sql/001_operational_schema.sql", "fabric/sql/002_analytics_views.sql",
    "fabric/power-bi/SupplyResponse.Report/.platform",
    "fabric/power-bi/SupplyResponse.SemanticModel/definition.pbism",
])
def test_non_generated_release_input_drift_changes_digest(tmp_path, relative):
    from fabric.report_contract import artifact_digest

    shutil.copytree(ROOT / "fabric", tmp_path / "fabric")
    before = artifact_digest(tmp_path)
    path = tmp_path / relative
    path.write_bytes(path.read_bytes() + b"\n")
    assert artifact_digest(tmp_path) != before


@pytest.mark.parametrize("relative", [
    "fabric/power-bi/SupplyResponse.Report/definition/pages/command-center/page.json",
    "fabric/power-bi/SupplyResponse.SemanticModel/definition/tables/SavedAnalyses.tmdl",
    "fabric/reporting/queries/SavedAnalyses.sql",
])
def test_generated_or_query_drift_fails_before_digest_can_be_accepted(tmp_path, relative):
    from fabric.report_contract import artifact_digest

    shutil.copytree(ROOT / "fabric", tmp_path / "fabric")
    path = tmp_path / relative
    path.write_text("corrupt", encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        artifact_digest(tmp_path)


def test_artifact_symlinks_are_rejected(tmp_path):
    from fabric.report_contract import artifact_digest

    shutil.copytree(ROOT / "fabric", tmp_path / "fabric")
    path = tmp_path / "fabric/sql/002_analytics_views.sql"
    path.unlink()
    path.symlink_to(ROOT / "fabric/sql/002_analytics_views.sql")
    with pytest.raises(ValueError, match="symlink"):
        artifact_digest(tmp_path)
```

- [x] Add this field immediately after `power_bi_deployment_receipt` in `apps/api/app/settings.py`:

```python
    power_bi_reporting_receipt: str | None = None
```

- [x] Create `fabric/report_contract.py` with the code below. This local tool prints a reviewed Python source file; it cannot issue a receipt or change environment settings. It validates generator equality before hashing actual bytes. Including paths and lengths through canonical JSON removes concatenation ambiguity; item metadata, connection parameter templates, SQL schema/view sources, partition queries and all native artifacts are included. Source SQL changes require a new digest even if the output remains structurally valid.

```python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fabric import report_model, report_pages

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ("SupplyResponse.Report", "SupplyResponse.SemanticModel")


def artifact_digest(root: Path) -> str:
    roots = [root / "fabric/power-bi" / item for item in ITEMS]
    roots += [root / "fabric/reporting/queries", root / "fabric/sql"]
    paths: list[Path] = []
    for directory in roots:
        if not directory.is_dir():
            raise ValueError(f"missing reporting input directory: {directory}")
        for path in (directory, *directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"reporting input symlink: {path}")
            if path.is_file():
                paths.append(path)
    report_pages.verify(root / "fabric/power-bi/SupplyResponse.Report/definition")
    report_model.verify(
        root / "fabric/power-bi/SupplyResponse.SemanticModel/definition",
        root / "fabric/reporting/queries",
    )
    entries = [
        [path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()]
        for path in sorted(paths, key=lambda path: path.relative_to(root).as_posix())
    ]
    payload = ["supply-response-reporting-artifacts-v1", entries]
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def generated_module(root: Path) -> str:
    digest = artifact_digest(root)
    return (
        '# Generated by python -m fabric.report_contract; do not edit the digest.\n'
        '# This identifies local artifacts, not a deployed or available report.\n'
        'REPORTING_CONTRACT = "saved-analysis-v1"\n'
        f'REPORTING_ARTIFACT_SHA256 = "{digest}"\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = generated_module(ROOT)
    if args.check:
        target = ROOT / "apps/api/app/_reporting_artifact.py"
        if not target.is_file() or target.read_text(encoding="utf-8") != expected:
            raise SystemExit("API reporting artifact digest is stale; regenerate and review")
    else:
        print(expected, end="")


if __name__ == "__main__":
    main()
```

- [x] Run `.venv/bin/python -m fabric.report_contract` after artifact integration. Create `apps/api/app/_reporting_artifact.py` using `apply_patch` with the exact four lines printed by that command. No literal digest is supplied in this plan because the companion generator implementation has not finished; computing it from the final verified artifacts is mandatory, not a discretionary implementation choice. Never use an all-zero digest, environment-provided expected digest, self-reported receipt digest or catch-and-default import.

- [x] Add imports `hmac`, `json`, `re` and the following import to `apps/api/app/readiness.py`, then append the complete verifier below. Existing readiness classes/functions are untouched.

```python
from apps.api.app._reporting_artifact import (
    REPORTING_ARTIFACT_SHA256,
    REPORTING_CONTRACT,
)

_REPORT_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_REPORT_URL = re.compile(
    rf"https://app\.powerbi\.com/groups/{_REPORT_UUID}/reports/{_REPORT_UUID}"
)


def verify_power_bi_reporting_receipt(
    report_url: str | None,
    fabric_sql_server: str | None,
    fabric_sql_database: str | None,
    receipt: str | None,
) -> bool:
    """Match trusted release attestation; performs no availability or access check."""
    if (
        report_url is None
        or _REPORT_URL.fullmatch(report_url) is None
        or fabric_sql_server is None
        or not fabric_sql_server.strip()
        or fabric_sql_database is None
        or not fabric_sql_database.strip()
        or receipt is None
        or re.fullmatch(r"[0-9a-f]{64}", receipt) is None
    ):
        return False
    payload = [
        "supply-response-reporting-receipt-v1",
        REPORTING_CONTRACT,
        REPORTING_ARTIFACT_SHA256,
        report_url,
        fabric_sql_server,
        fabric_sql_database,
    ]
    expected = hashlib.sha256(json.dumps(
        payload, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return hmac.compare_digest(receipt, expected)
```

- [x] In `apps/api/app/routes/health.py` add the following imports:

```python
from apps.api.app._reporting_artifact import REPORTING_CONTRACT
from apps.api.app.readiness import verify_power_bi_reporting_receipt
```

Inside the existing live `deployment_contract` dictionary, after `tenant_sharepoint_host`, insert this dictionary unpacking. Keep its enclosing live/fallback conditional and every existing field intact:

```python
                **(
                    {"power_bi_reporting_contract": REPORTING_CONTRACT}
                    if power_bi_available
                    and verify_power_bi_reporting_receipt(
                        services.power_bi_url,
                        services.settings.fabric_sql_server,
                        services.settings.fabric_sql_database,
                        services.settings.power_bi_reporting_receipt,
                    )
                    else {}
                ),
```

Use the composed `services.power_bi_url`, which is exactly what the response exposes, rather than a second raw URL setting. This prevents a receipt for one URL advertising compatibility for another injected/composed URL. Receipt verification belongs here because both old readiness and actual response URL are available here; adding a boolean to `FabricBoundReadiness` would duplicate state without improving the trust boundary.

- [x] Run the targeted checks and then the existing compatibility cases. The first command after full implementation must report all tests passing, including positive activation and all negative gates. Generator and project suites were already required by artifact integration; rerun if the digest checks find drift, not to paper over it.

```sh
.venv/bin/pytest tests/test_reporting_activation.py tests/test_api.py tests/api/test_failure_contracts.py -o addopts='' -q
.venv/bin/python -m fabric.report_contract --check
.venv/bin/ruff check fabric/report_contract.py apps/api/app/_reporting_artifact.py apps/api/app/readiness.py apps/api/app/settings.py apps/api/app/routes/health.py tests/test_reporting_activation.py
git diff --check
```

Do not modify exact legacy expected payloads to add an empty/null contract key. Unconfigured behavior should be byte-for-byte structurally compatible. Do not execute live test modules. Record RED/GREEN and the final generated digest in the task report, then hand the diff to the controller; this design task itself creates no production files and makes no commit.

## Separate coordinated release issuance gate (not implemented or executed here)

Controller integration correction: the repository's normal Ruff formatter wraps
the long digest assignment. `generated_module` must emit that stable parenthesized
multiline assignment directly, then the packaged module must match its output
exactly. The digest value and receipt encoding are unchanged. Verify with
`ruff format --check` and the exact generated-module test; do not bypass hooks
or weaken the equality assertion. This supersedes the four-line output wording
above only.

The digest records source artifact identity, including parameterized connection templates; the receipt adds the exact substituted Fabric SQL server/database and canonical report URL. Issuance must follow all of these authorized release checks:

1. Use the same reviewed source revision and API digest as the packaged release. Run generator equality, vendored schema, locked TOM and saved-reporting SQL tests. Verify the staged substituted artifacts are those outputs except for the already-supported server/database substitution, and preserve report/model logical IDs.
2. Verify the target database contains the matching reporting views and source contracts, and publish/verify the matching model and report at the exact report URL. Check the report's semantic-model association and model connection binding. URL existence or publication success alone is insufficient.
3. Execute separately approved read-only DAX acceptance using existing saved multi-case and historical-analysis fixtures: exact case/analysis/record/option selection, ambiguous/missing selections, unknown values, grouped visual rows and no cross-case leakage. Inspect all eight native pages, case selector sync, focused URL navigation, recommendation/approval and simulated/observed labeling. The existing live smoke test creates scenario state; do not run it under a read-only gate.
4. Record acceptance evidence tied to the API artifact digest, exact URL/server/database and release revision. Only an explicitly authorized coordinated release may then compute the SHA-256 of the canonical JSON array shown in the independent test encoder and set `SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT`. This plan intentionally adds no issuance command, settings propagation or deploy automation.
5. Verify `/api/runtime` advertises the contract and the frontend opens the exact reviewed saved selection. If publication, SQL, model binding or acceptance differs, do not issue the receipt. Invalidate/remove it whenever deployed report/model/SQL bindings change or the acceptance evidence is no longer applicable.

Receipt matching does not poll Power BI, validate user permission, guarantee licensing, refresh data, execute DAX or establish current availability. Those remain release evidence and existing service/user access concerns. A same-URL remote overwrite cannot be detected by this offline gate; invalidation is part of release ownership. This limitation must accompany any release handoff.
