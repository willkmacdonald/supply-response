from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.execution.playback import ImmediateClock


def _app(tmp_path, *, enabled: bool):
    clock = ImmediateClock(datetime.now(UTC))
    return create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'fault-support.db'}",
            automated_test_faults_enabled=enabled,
        ),
        clock=clock.now,
        playback_clock=clock,
    )


def _create(client: TestClient, purpose: str) -> str:
    response = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": purpose},
    )
    assert response.status_code == 201
    return response.json()["case_id"]


def _approve(client: TestClient, case_id: str) -> dict:
    analysis = client.post(f"/api/cases/{case_id}/analysis")
    assert analysis.status_code == 201
    response = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": f"RL-E2E-{case_id}"},
        json={
            "analysis_id": analysis.json()["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_automated_fault_route_is_absent_when_disabled(tmp_path):
    app = _app(tmp_path, enabled=False)
    with TestClient(app) as client:
        case_id = _create(client, "automated_test")
        response = client.post(f"/api/test/cases/{case_id}/faults/planning_failure")

    assert response.status_code == 404


def test_showcase_case_cannot_arm_a_fault_even_in_test_configuration(tmp_path):
    app = _app(tmp_path, enabled=True)
    with TestClient(app) as client:
        case_id = _create(client, "showcase")
        response = client.post(f"/api/test/cases/{case_id}/faults/planning_failure")

    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "AUTOMATED_TEST_CASE_REQUIRED"}


def test_planning_fault_fails_once_then_real_retry_completes(tmp_path):
    app = _app(tmp_path, enabled=True)
    with TestClient(app) as client:
        case_id = _create(client, "automated_test")
        armed = client.post(f"/api/test/cases/{case_id}/faults/planning_failure")
        decision = _approve(client, case_id)
        app.state.services.planning_worker.process_next_unattempted_outbox()
        failed = client.get(f"/api/decisions/{decision['decision_id']}")
        retried = client.post(f"/api/decisions/{decision['decision_id']}/actions/retry")

    assert armed.status_code == 204
    assert failed.json()["action_planning_status"] == "failed"
    assert retried.status_code == 200
    assert retried.json()["action_planning_status"] == "complete"


def test_failed_action_fault_uses_the_real_retry_transition(tmp_path):
    app = _app(tmp_path, enabled=True)
    with TestClient(app) as client:
        case_id = _create(client, "automated_test")
        armed = client.post(f"/api/test/cases/{case_id}/faults/first_action_failure")
        decision = _approve(client, case_id)
        app.state.services.planning_worker.process_next_unattempted_outbox()
        actions = client.get(f"/api/decisions/{decision['decision_id']}/actions").json()
        failed = next(action for action in actions if action["status"] == "failed")
        retried = client.post(
            f"/api/decisions/{decision['decision_id']}/actions/"
            f"{failed['action_id']}/retry"
        )

    assert armed.status_code == 204
    assert retried.status_code == 200
    assert retried.json()["action_id"] == failed["action_id"]
    assert retried.json()["status"] == "in_progress"
