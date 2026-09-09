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


def receipt_for(
    *, url=URL, server=SERVER, database=DATABASE, digest=None, contract=CONTRACT
):
    # Independent protocol encoder: never call the production verifier to mint tests.
    from apps.api.app._reporting_artifact import REPORTING_ARTIFACT_SHA256

    payload = [
        "supply-response-reporting-receipt-v1",
        contract,
        REPORTING_ARTIFACT_SHA256 if digest is None else digest,
        url,
        server,
        database,
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def runtime_payload(
    tmp_path,
    *,
    receipt=None,
    url=URL,
    composed_url=None,
    server=SERVER,
    database=DATABASE,
    verified=True,
    health="ready",
    mode=RuntimeMode.LIVE,
):
    if composed_url is None:
        composed_url = url
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
        services = build_composition(
            settings,
            live_components={
                "store": sqlite_store(settings.database_url, runtime_mode=mode),
                "analysis_service": object(),
                "auth_service": object(),
                "power_bi_url": composed_url,
                "readiness": Readiness(),
            },
        )
    else:
        services = build_composition(settings)
        # Even an erroneously injected positive readiness cannot enable fallback.
        services.readiness = Readiness()
        services.power_bi_url = composed_url
    with TestClient(create_app(services=services)) as client:
        response = client.get("/api/runtime")
        assert response.status_code == 200
        return response.json()


def test_exact_release_attestation_exposes_contract(tmp_path):
    payload = runtime_payload(tmp_path, receipt=receipt_for())
    assert payload["power_bi_available"] is True
    assert payload["deployment_contract"][KEY] == CONTRACT


def test_raw_settings_url_receipt_does_not_attest_composed_report_url(tmp_path):
    composed_url = URL.replace("22222222", "33333333")
    payload = runtime_payload(
        tmp_path,
        url=URL,
        composed_url=composed_url,
        receipt=receipt_for(url=URL),
    )
    assert payload["power_bi_url"] == composed_url
    assert KEY not in payload["deployment_contract"]


def test_composed_report_url_receipt_attests_composed_report_url(tmp_path):
    composed_url = URL.replace("22222222", "33333333")
    payload = runtime_payload(
        tmp_path,
        url=URL,
        composed_url=composed_url,
        receipt=receipt_for(url=composed_url),
    )
    assert payload["power_bi_url"] == composed_url
    assert payload["deployment_contract"][KEY] == CONTRACT


@pytest.mark.parametrize("receipt", [None, "", "garbage", "0" * 64])
def test_absent_or_invalid_receipt_keeps_old_readiness_without_new_links(
    tmp_path, receipt
):
    payload = runtime_payload(tmp_path, receipt=receipt)
    assert payload["power_bi_available"] is True
    assert KEY not in payload["deployment_contract"]


def test_legacy_url_receipt_does_not_attest_saved_reporting(tmp_path):
    old = hashlib.sha256(URL.encode()).hexdigest()
    payload = runtime_payload(tmp_path, receipt=old)
    assert payload["power_bi_available"] is True
    assert KEY not in payload["deployment_contract"]


@pytest.mark.parametrize(
    "change",
    [
        {"digest": "0" * 64},
        {"contract": "saved-analysis-v0"},
        {"url": URL.replace("22222222", "33333333")},
        {"server": "other.fabric.microsoft.com"},
        {"database": "other"},
    ],
)
def test_receipt_must_match_every_release_binding(tmp_path, change):
    payload = runtime_payload(tmp_path, receipt=receipt_for(**change))
    assert KEY not in payload["deployment_contract"]


@pytest.mark.parametrize(
    "url",
    [
        URL + "/",
        URL + "/command-center",
        URL + "?filter=x",
        URL + "#page",
        URL.replace("https://", "http://"),
        URL.replace("app.powerbi.com", "example.com"),
        URL.replace("app.powerbi.com", "app.powerbi.com:443"),
        URL.replace("app.powerbi.com", "user@app.powerbi.com"),
        URL.replace("app.powerbi.com", "APP.POWERBI.COM"),
        "https://app.powerbi.com/groups/demo/reports/report",
        " " + URL,
        URL + "\n",
        URL.replace("/groups/", "/groups/%31"),
    ],
)
def test_even_matching_receipt_cannot_activate_invalid_report_url(tmp_path, url):
    payload = runtime_payload(tmp_path, url=url, receipt=receipt_for(url=url))
    assert KEY not in payload["deployment_contract"]


@pytest.mark.parametrize(
    "change",
    [
        {"verified": False},
        {"health": "unverified"},
        {"health": "unavailable"},
    ],
)
def test_attestation_does_not_replace_existing_readiness(tmp_path, change):
    payload = runtime_payload(tmp_path, receipt=receipt_for(), **change)
    assert payload["power_bi_available"] is False
    assert KEY not in payload["deployment_contract"]


def test_fallback_cannot_expose_reporting_contract(tmp_path):
    payload = runtime_payload(
        tmp_path, receipt=receipt_for(), mode=RuntimeMode.FALLBACK
    )
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


@pytest.mark.parametrize(
    "relative",
    [
        "fabric/sql/001_operational_schema.sql",
        "fabric/sql/002_analytics_views.sql",
        "fabric/power-bi/SupplyResponse.Report/.platform",
        "fabric/power-bi/SupplyResponse.SemanticModel/definition.pbism",
    ],
)
def test_non_generated_release_input_drift_changes_digest(tmp_path, relative):
    from fabric.report_contract import artifact_digest

    shutil.copytree(ROOT / "fabric", tmp_path / "fabric")
    before = artifact_digest(tmp_path)
    path = tmp_path / relative
    path.write_bytes(path.read_bytes() + b"\n")
    assert artifact_digest(tmp_path) != before


@pytest.mark.parametrize(
    "relative",
    [
        "fabric/power-bi/SupplyResponse.Report/definition/pages/command-center/page.json",
        "fabric/power-bi/SupplyResponse.SemanticModel/definition/tables/SavedAnalyses.tmdl",
        "fabric/reporting/queries/SavedAnalyses.sql",
    ],
)
def test_generated_or_query_drift_fails_before_digest_can_be_accepted(
    tmp_path, relative
):
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
