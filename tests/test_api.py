from fastapi.testclient import TestClient

from apps.api.app.main import CASES, DECISIONS, app
from data.synthetic.rl001 import OperationalSnapshot


client = TestClient(app)


def setup_function():
    CASES.clear()
    DECISIONS.clear()


def create_case() -> str:  # allowed - shared API test fixture
    response = client.post(
        "/api/cases",
        json={
            "disruption": OperationalSnapshot.rl001().disruption.model_dump(mode="json")
        },
    )
    assert response.status_code == 201
    assert response.json()["case"]["status"] == "open"
    return response.json()["case"]["case_id"]


def analyze(case_id: str) -> dict:
    response = client.post(f"/api/cases/{case_id}/analyze")
    assert response.status_code == 200
    return response.json()


def alex_decision(option_id: str) -> dict:  # allowed - shared API test fixture
    return {
        "option_id": option_id,
        "actor": {
            "persona_id": "RL-PERSONA-ALEX",
            "roles": ["material_planner", "response_approver"],
            "identity_source": "entra",
            "source_id": "RL-ENTRA-ALEX",
        },
    }


def test_api_returns_canonical_analysis_version_and_response_options():
    case_id = create_case()

    analysis = analyze(case_id)
    options = client.get(f"/api/cases/{case_id}/options")

    assert analysis["case_id"] == case_id
    assert analysis["ranking"]["recommended_option_id"] == "RL-OPTION-COMBINED"
    assert analysis["ranking"]["policy_version"] == "thresholded-lexicographic-v1"
    assert options.status_code == 200
    assert {option["option_id"] for option in options.json()} == {
        "RL-OPTION-NO-MITIGATION",
        "RL-OPTION-EXPEDITE",
        "RL-OPTION-TRANSFER",
        "RL-OPTION-RESEQUENCE",
        "RL-OPTION-BETA",
        "RL-OPTION-COMBINED",
    }
    assert client.get(f"/api/cases/{case_id}").json()["analysis"]["analysis_id"]


def test_api_analysis_uses_causal_utc_wall_clock_timestamps():
    case_id = create_case()

    analysis = analyze(case_id)

    assert (
        analysis["analysis_started_at"]
        != analysis["material"]["scenario_effective_time"]
    )
    assert analysis["analysis_started_at"].endswith("Z")
    assert analysis["created_at"] >= analysis["analysis_started_at"]
    assert all(
        analysis["analysis_started_at"]
        <= item["retrieved_at"]
        <= analysis["created_at"]
        for item in analysis["evidence_items"]
    )


def test_cannot_approve_an_infeasible_response_option():
    case_id = create_case()
    analyze(case_id)

    response = client.post(
        f"/api/cases/{case_id}/approve",
        json=alex_decision("RL-OPTION-BETA"),
    )

    assert response.status_code == 409
    assert DECISIONS == []


def test_decision_references_the_immutable_analysis_and_option():
    case_id = create_case()
    analysis = analyze(case_id)

    response = client.post(
        f"/api/cases/{case_id}/approve",
        json=alex_decision("RL-OPTION-COMBINED"),
    )

    assert response.status_code == 200
    assert response.json()["selected_option_id"] == "RL-OPTION-COMBINED"
    assert response.json()["case"]["status"] == "action_planning"
    assert len(DECISIONS) == 1
    assert DECISIONS[0].analysis_id == analysis["analysis_id"]
    assert DECISIONS[0].option_id == "RL-OPTION-COMBINED"
    assert DECISIONS[0].satisfied_prerequisite_roles == (
        "finance_approver",
        "material_planner",
    )


def test_approval_rejects_missing_analysis_prerequisite_satisfaction():
    case_id = create_case()
    analyze(case_id)
    record = CASES[case_id]
    record.analysis = record.analysis.model_copy(update={"approval_satisfactions": ()})

    response = client.post(
        f"/api/cases/{case_id}/approve",
        json=alex_decision("RL-OPTION-COMBINED"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Response option prerequisite approvals are not satisfied: finance_approver"
    )
    assert record.case.status == "awaiting_decision"
    assert record.selected_option_id is None
    assert DECISIONS == []


def test_dashboard_summary_uses_canonical_case_statuses():
    empty = client.get("/api/dashboard/summary")
    case_id = create_case()
    analyze(case_id)

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    assert response.json()["active_disruptions"] == 1
    assert response.json()["analyzed_cases"] == 1
    assert empty.json()["revenue_at_risk"] == "0.00"
    assert response.json()["revenue_at_risk"] == "955000.00"
