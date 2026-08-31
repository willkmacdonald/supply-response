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


def test_cannot_approve_an_infeasible_response_option():
    case_id = create_case()
    analyze(case_id)

    response = client.post(
        f"/api/cases/{case_id}/approve",
        json={"option_id": "RL-OPTION-BETA"},
    )

    assert response.status_code == 409
    assert DECISIONS == []


def test_decision_references_the_immutable_analysis_and_option():
    case_id = create_case()
    analysis = analyze(case_id)

    response = client.post(
        f"/api/cases/{case_id}/approve",
        json={"option_id": "RL-OPTION-COMBINED"},
    )

    assert response.status_code == 200
    assert response.json()["selected_option_id"] == "RL-OPTION-COMBINED"
    assert response.json()["case"]["status"] == "action_planning"
    assert len(DECISIONS) == 1
    assert DECISIONS[0].analysis_id == analysis["analysis_id"]
    assert DECISIONS[0].option_id == "RL-OPTION-COMBINED"


def test_dashboard_summary_uses_canonical_case_statuses():
    case_id = create_case()
    analyze(case_id)

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    assert response.json()["active_disruptions"] == 1
    assert response.json()["analyzed_cases"] == 1
