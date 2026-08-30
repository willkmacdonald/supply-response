import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import ACTION_LEDGER, CASES, DATASET, app

client = TestClient(app)


def setup_function():
    CASES.clear()
    ACTION_LEDGER.clear()


def create_and_analyze():  # allowed - shared API test fixture, not application logic
    r = client.post(
        "/api/cases",
        json={"disruption": DATASET.disruptions[0].model_dump(mode="json")},
    )
    assert r.status_code == 201
    case_id = r.json()["case_id"]
    r = client.post(f"/api/cases/{case_id}/analyze")
    assert r.status_code == 200
    return case_id, r.json()


def test_api_contract_create_get_analyze_and_scenarios():
    case_id, analysis = create_and_analyze()
    assert analysis["exposure"]["metadata"]["calculation_version"] == "exposure-v1"
    assert len(analysis["scenarios"]) == 6
    assert client.get(f"/api/cases/{case_id}").status_code == 200
    assert client.get(f"/api/cases/{case_id}/scenarios").status_code == 200


def test_analysis_uses_the_disruption_plant():
    disruption = DATASET.disruptions[0].model_copy(update={"plant_id": "RL-PLANT-DAL"})
    response = client.post(
        "/api/cases",
        json={"disruption": disruption.model_dump(mode="json")},
    )
    case_id = response.json()["case_id"]

    analysis = client.post(f"/api/cases/{case_id}/analyze")

    assert response.status_code == 201
    assert analysis.status_code == 200
    assert analysis.json()["exposure"]["usable_inventory"] == 1500


def test_cannot_approve_non_executable_beta_scenario():
    case_id, _ = create_and_analyze()
    r = client.post(
        f"/api/cases/{case_id}/approve",
        json={"scenario_id": "RL-SCENARIO-5", "evidence_refs": ["RL-QUALITY-001"]},
    )
    assert r.status_code == 409
    assert ACTION_LEDGER == []


def test_approval_writes_action_ledger():
    case_id, _ = create_and_analyze()
    r = client.post(
        f"/api/cases/{case_id}/approve",
        json={"scenario_id": "RL-SCENARIO-2", "evidence_refs": ["RL-001"]},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert len(ACTION_LEDGER) == 1
    assert ACTION_LEDGER[0].scenario_id == "RL-SCENARIO-2"


@pytest.mark.parametrize("caller_evidence", [[], ["RL-SPOOFED-CALLER-EVIDENCE"]])
def test_action_ledger_preserves_server_owned_scenario_and_calculation_evidence(
    caller_evidence,
):
    case_id, analysis = create_and_analyze()
    selected_scenario = next(
        scenario
        for scenario in analysis["scenarios"]
        if scenario["scenario_id"] == "RL-SCENARIO-5"
    )

    response = client.post(
        f"/api/cases/{case_id}/reject",
        json={
            "scenario_id": selected_scenario["scenario_id"],
            "evidence_refs": caller_evidence,
        },
    )

    assert response.status_code == 200
    record = ACTION_LEDGER[0]
    assert record.scenario_evidence_refs == tuple(selected_scenario["evidence_refs"])
    assert record.scenario_evidence_refs == ("RL-QUALITY-001",)
    assert record.approval_evidence_refs == tuple(caller_evidence)
    assert (
        record.calculation_version
        == analysis["exposure"]["metadata"]["calculation_version"]
    )
    assert record.source_data_lineage == tuple(
        analysis["exposure"]["metadata"]["source_data_lineage"]
    )
    assert record.source_data_lineage
    assert "RL-SPOOFED-CALLER-EVIDENCE" not in record.source_data_lineage


def test_dashboard_summary_contract():
    create_and_analyze()
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    assert r.json()["active_disruptions"] == 1
