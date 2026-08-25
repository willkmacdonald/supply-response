"""API contract tests using the FastAPI test client and an isolated SQLite file."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from data.fixtures.demo import DEMO_DISRUPTION_ID, QUALITY_CONSTRAINT_ID, demo_dataset


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    db_path = tmp_path_factory.mktemp("db") / "test_supply_response.db"
    os.environ["SUPPLY_RESPONSE_DB_URL"] = f"sqlite:///{db_path}"

    # Import after the environment is set so the engine binds to the test file.
    import importlib

    from apps.api import database as database_module

    importlib.reload(database_module)
    from apps.api import dataset as dataset_module
    from apps.api import main as main_module
    from apps.api import services as services_module
    from apps.api.routers import cases as cases_module
    from apps.api.routers import dashboard as dashboard_module

    importlib.reload(services_module)
    importlib.reload(cases_module)
    importlib.reload(dashboard_module)
    importlib.reload(main_module)

    dataset_module.set_dataset(demo_dataset())
    database_module.init_db()

    with TestClient(main_module.app) as test_client:
        yield test_client

    dataset_module.reset_dataset()
    Path(db_path).unlink(missing_ok=True)
    os.environ.pop("SUPPLY_RESPONSE_DB_URL", None)


@pytest.fixture(scope="module")
def case_id(client: TestClient) -> str:
    response = client.post("/api/cases", json={"disruption_id": DEMO_DISRUPTION_ID})
    assert response.status_code == 201, response.text
    return response.json()["case_id"]


def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["calculation_version"]


def test_create_case(client: TestClient, case_id: str):
    response = client.get(f"/api/cases/{case_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"].startswith("RL-CASE-")
    assert body["disruption_id"] == DEMO_DISRUPTION_ID
    assert body["status"] == "new"
    assert body["disruption"]["delayed_qty"] == 8000
    assert any("8000" in fact or "8,000" in fact for fact in body["facts"])
    assert any(QUALITY_CONSTRAINT_ID in item for item in body["uncertainties"])
    assert len(body["evidence"]) == 3


def test_create_case_unknown_disruption(client: TestClient):
    response = client.post("/api/cases", json={"disruption_id": "RL-999"})
    assert response.status_code == 404


def test_get_unknown_case(client: TestClient):
    assert client.get("/api/cases/RL-CASE-999999").status_code == 404


def test_scenarios_before_analysis(client: TestClient):
    created = client.post("/api/cases", json={"disruption_id": DEMO_DISRUPTION_ID})
    fresh_case = created.json()["case_id"]
    response = client.get(f"/api/cases/{fresh_case}/scenarios")
    assert response.status_code == 409


def test_analyze_case(client: TestClient, case_id: str):
    response = client.post(f"/api/cases/{case_id}/analyze")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["exposure"]["usable_inventory"] == 4000
    assert body["exposure"]["first_stockout_date"] == "2025-09-05"
    assert body["exposure"]["revenue_at_risk"] == 1_071_000.0
    assert len(body["scenarios"]) == 6
    assert body["recommended_scenario_id"] == "RL-SCN-006"
    assert body["uncertainties"]


def test_analyze_is_idempotent(client: TestClient, case_id: str):
    first = client.post(f"/api/cases/{case_id}/analyze").json()
    second = client.post(f"/api/cases/{case_id}/analyze").json()
    assert [s["scenario_id"] for s in first["scenarios"]] == [
        s["scenario_id"] for s in second["scenarios"]
    ]
    assert [s["score"] for s in first["scenarios"]] == [
        s["score"] for s in second["scenarios"]
    ]
    scenarios = client.get(f"/api/cases/{case_id}/scenarios").json()["scenarios"]
    assert len(scenarios) == 6


def test_get_scenarios(client: TestClient, case_id: str):
    response = client.get(f"/api/cases/{case_id}/scenarios")
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_scenario_id"] == "RL-SCN-006"
    ranks = [scenario["rank"] for scenario in body["scenarios"]]
    assert ranks == sorted(ranks)
    beta = next(s for s in body["scenarios"] if s["scenario_id"] == "RL-SCN-005")
    assert beta["executable"] is False
    assert QUALITY_CONSTRAINT_ID in beta["blocking_constraint"]


def test_approve_rejects_non_executable_scenario(client: TestClient, case_id: str):
    response = client.post(
        f"/api/cases/{case_id}/approve",
        json={"scenario_id": "RL-SCN-005", "decided_by": "Alex Morgan"},
    )
    assert response.status_code == 409
    assert QUALITY_CONSTRAINT_ID in response.json()["detail"]


def test_approve_unknown_scenario(client: TestClient, case_id: str):
    response = client.post(
        f"/api/cases/{case_id}/approve", json={"scenario_id": "RL-SCN-999"}
    )
    assert response.status_code == 404


def test_reject_scenario(client: TestClient):
    created = client.post("/api/cases", json={"disruption_id": DEMO_DISRUPTION_ID}).json()
    client.post(f"/api/cases/{created['case_id']}/analyze")
    response = client.post(
        f"/api/cases/{created['case_id']}/reject",
        json={"scenario_id": "RL-SCN-002", "rationale": "Freight cost is too high."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["action"]["status"] == "rejected"
    assert body["bounded_actions"] == []


def test_approve_writes_action_ledger(client: TestClient, case_id: str):
    response = client.post(
        f"/api/cases/{case_id}/approve",
        json={
            "scenario_id": "RL-SCN-006",
            "decided_by": "Alex Morgan",
            "rationale": "Best net benefit with the lowest OTIF exposure.",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"

    action = body["action"]
    assert action["action_id"].startswith("RL-ACT-")
    assert action["scenario_id"] == "RL-SCN-006"
    assert action["decided_by"] == "Alex Morgan"
    assert action["calculation_version"]
    assert action["evidence"]
    assert action["predicted_cost"] == 35_800.0
    assert action["predicted_revenue_protected"] == 777_000.0

    tasks = " ".join(body["bounded_actions"])
    assert "recovery request" in tasks
    assert "Procurement" in tasks
    assert "Quality" in tasks

    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["status"] == "approved"
    assert len(detail["actions"]) >= 1


def test_dashboard_summary(client: TestClient, case_id: str):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["cases_by_status"]
    assert body["approved_actions"] >= 1
    assert body["rejected_actions"] >= 1
    assert body["total_revenue_at_risk"] > 0
    assert body["dataset_row_counts"]["response_scenarios"] == 6
    assert any(case["case_id"] == case_id for case in body["cases"])
    assert body["average_minutes_to_decision"] is not None


def test_list_cases(client: TestClient):
    response = client.get("/api/cases")
    assert response.status_code == 200
    assert len(response.json()) >= 3


def test_openapi_contract_exposes_required_endpoints(client: TestClient):
    paths = client.get("/openapi.json").json()["paths"]
    for path, method in [
        ("/api/cases", "post"),
        ("/api/cases/{case_id}", "get"),
        ("/api/cases/{case_id}/analyze", "post"),
        ("/api/cases/{case_id}/scenarios", "get"),
        ("/api/cases/{case_id}/approve", "post"),
        ("/api/cases/{case_id}/reject", "post"),
        ("/api/dashboard/summary", "get"),
    ]:
        assert path in paths, path
        assert method in paths[path], f"{method} {path}"


def test_narrative_before_analysis(client: TestClient):
    created = client.post("/api/cases", json={"disruption_id": DEMO_DISRUPTION_ID})
    fresh_case = created.json()["case_id"]
    response = client.get(f"/api/cases/{fresh_case}/narrative")
    assert response.status_code == 409


def test_narrative_after_analysis(client: TestClient, case_id: str):
    response = client.get(f"/api/cases/{case_id}/narrative")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["case_id"] == case_id
    assert len(body["narrative"]) > 50
    assert body["source"] in {"deterministic", "azure_openai"}
    assert body["agent_version"]
    # Recommended scenario must appear in the narrative
    assert "RL-SCN-006" in body["narrative"]


def test_narrative_unknown_case(client: TestClient):
    assert client.get("/api/cases/RL-CASE-999999/narrative").status_code == 404
