from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.execution.worker import ActionPlanningWorker


def create_and_analyze(  # allowed - shared API test fixture
    client,
    *,
    purpose="automated_test",
):
    created = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": purpose},
    )
    assert created.status_code == 201
    case_id = created.json()["case_id"]
    analyzed = client.post(f"/api/cases/{case_id}/analysis")
    assert analyzed.status_code == 201
    return case_id, analyzed.json()


def approve(  # allowed - shared API test fixture
    client,
    case_id,
    analysis_id,
    *,
    key="RL-API-DECISION-1",
):
    return client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": key},
        json={
            "analysis_id": analysis_id,
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )


def test_runtime_contract_is_server_owned_and_cannot_be_overridden(client):
    runtime = client.get("/api/runtime?runtime_mode=live")
    overridden = client.post(
        "/api/cases",
        json={
            "template_id": "RL-001",
            "purpose": "automated_test",
            "runtime_mode": "live",
        },
    )

    assert runtime.json() == {
        "runtime_mode": "fallback",
        "work_iq": "synthetic",
        "operational_store": "sqlite",
        "agent_runtime": "local",
        "power_bi_available": False,
        "power_bi_url": None,
        "capability_health": {
            "operational_store": "ready",
            "work_iq": "ready",
            "agent_runtime": "ready",
            "power_bi": "unavailable",
        },
        "deployment_contract": None,
    }
    assert overridden.status_code == 422


def test_decision_rejects_stale_analysis_with_exact_detail(client):
    case_id, first = create_and_analyze(client)
    second = client.post(f"/api/cases/{case_id}/analysis")
    assert second.status_code == 201

    response = approve(client, case_id, first["analysis_id"])

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "STALE_ANALYSIS",
        "message": "Create a new Analysis Version before deciding.",
    }


def test_non_executable_option_returns_blocking_codes(client):
    case_id, analysis = create_and_analyze(client)

    response = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-BETA"},
        json={
            "analysis_id": analysis["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-BETA",
        },
    )

    beta = next(
        item
        for item in analysis["response_options"]
        if item["option_id"] == "RL-OPTION-BETA"
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "OPTION_NOT_EXECUTABLE",
        "blocking_codes": beta["blocking_codes"],
    }


def test_missing_response_approver_role_returns_exact_detail(client, services):
    case_id, analysis = create_and_analyze(client)
    services.identity = services.identity.model_copy(
        update={"effective_roles": ("material_planner",)}
    )

    response = approve(client, case_id, analysis["analysis_id"])

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "ROLE_REQUIRED",
        "role": "response_approver",
    }


def test_rejection_creates_no_actions_and_leaves_new_analysis_control(client, services):
    case_id, analysis = create_and_analyze(client)
    rejected = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-REJECTION"},
        json={
            "analysis_id": analysis["analysis_id"],
            "kind": "rejected",
            "rejection_reason": "Use a refreshed supplier update.",
        },
    )
    assert rejected.status_code == 201
    decision = rejected.json()

    services.run_worker_until_idle()
    actions = client.get(f"/api/decisions/{decision['decision_id']}/actions")
    case = client.get(f"/api/cases/{case_id}")
    refreshed = client.post(f"/api/cases/{case_id}/analysis")

    assert actions.json() == []
    assert decision["action_planning_status"] == "not_applicable"
    assert decision["new_analysis_available"] is True
    assert case.json()["controls"]["new_analysis"] is True
    assert refreshed.status_code == 201
    assert client.get(f"/api/cases/{case_id}").json()["status"] == "awaiting_decision"


def test_decision_idempotency_reuses_only_the_same_request(client):
    case_id, analysis = create_and_analyze(client)
    first = approve(client, case_id, analysis["analysis_id"], key="RL-API-SAME")
    second = approve(client, case_id, analysis["analysis_id"], key="RL-API-SAME")
    conflict = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-SAME"},
        json={
            "analysis_id": analysis["analysis_id"],
            "kind": "rejected",
            "rejection_reason": "Different request.",
        },
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["decision_id"] == second.json()["decision_id"]
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {"code": "IDEMPOTENCY_KEY_CONFLICT"}


def test_idempotent_decision_replay_precedes_stale_analysis_validation(client):
    case_id, first_analysis = create_and_analyze(client)
    first = approve(
        client,
        case_id,
        first_analysis["analysis_id"],
        key="RL-API-REPLAY-BEFORE-STALE",
    )
    assert first.status_code == 201
    newer_analysis = client.post(f"/api/cases/{case_id}/analysis")
    assert newer_analysis.status_code == 201

    replay = approve(
        client,
        case_id,
        first_analysis["analysis_id"],
        key="RL-API-REPLAY-BEFORE-STALE",
    )

    assert replay.status_code == 201
    assert replay.json()["decision_id"] == first.json()["decision_id"]


def test_decision_rejects_caller_owned_identity_and_provenance(client):
    case_id, analysis = create_and_analyze(client)
    response = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-UNTRUSTED"},
        json={
            "analysis_id": analysis["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
            "actor": {"roles": ["response_approver"]},
            "display_label": "Actual",
            "evidence": [],
        },
    )

    assert response.status_code == 422


def test_decision_request_shape_is_validated_before_domain_services(client):
    case_id, analysis = create_and_analyze(client)
    missing_option = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-MISSING-OPTION"},
        json={"analysis_id": analysis["analysis_id"], "kind": "approved"},
    )
    invalid_rejection = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-INVALID-REJECTION"},
        json={
            "analysis_id": analysis["analysis_id"],
            "kind": "rejected",
            "selected_option_id": "RL-OPTION-COMBINED",
            "rejection_reason": "No.",
        },
    )

    assert missing_option.status_code == 422
    assert invalid_rejection.status_code == 422


def test_planning_failure_is_visible_and_retryable(tmp_path):
    def fail_planning(decision):
        del decision
        raise RuntimeError("internal planning detail")

    settings = Settings(
        runtime_mode=RuntimeMode.FALLBACK,
        database_url=f"sqlite:///{tmp_path / 'planning-failure.db'}",
    )
    api = create_app(settings, planner=fail_planning, clock=lambda: datetime.now(UTC))
    with TestClient(api) as client:
        case_id, analysis = create_and_analyze(client)
        approved = approve(client, case_id, analysis["analysis_id"])
        assert approved.status_code == 201
        immutable = approved.json()
        services = api.state.services
        assert services.planning_worker.process_next_outbox() is True

        failed = client.get(f"/api/decisions/{immutable['decision_id']}")
        assert failed.json()["decision_id"] == immutable["decision_id"]
        assert failed.json()["action_planning_status"] == "failed"
        assert (
            client.get(f"/api/cases/{case_id}").json()["controls"][
                "retry_action_planning"
            ]
            is True
        )

        services.planning_worker = ActionPlanningWorker(services.uow_factory)
        retried = client.post(
            f"/api/decisions/{immutable['decision_id']}/actions/retry"
        )
        assert retried.status_code == 200
        assert retried.json()["decision_id"] == immutable["decision_id"]
        assert retried.json()["action_planning_status"] == "complete"
        assert (
            len(client.get(f"/api/decisions/{immutable['decision_id']}/actions").json())
            == 5
        )


def test_planning_retry_claims_only_the_requested_decision(tmp_path):
    def fail_planning(decision):
        del decision
        raise RuntimeError("internal planning detail")

    api = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'targeted-retry.db'}",
        ),
        planner=fail_planning,
        clock=lambda: datetime.now(UTC),
    )
    with TestClient(api) as client:
        first_case_id, first_analysis = create_and_analyze(client)
        first = approve(
            client,
            first_case_id,
            first_analysis["analysis_id"],
            key="RL-API-PENDING-A",
        ).json()
        second_case_id, second_analysis = create_and_analyze(client)
        second = approve(
            client,
            second_case_id,
            second_analysis["analysis_id"],
            key="RL-API-FAILED-B",
        ).json()
        services = api.state.services
        assert (
            services.planning_worker.process_decision_outbox(second["decision_id"])
            is True
        )
        assert (
            client.get(f"/api/decisions/{first['decision_id']}").json()[
                "action_planning_status"
            ]
            == "pending"
        )
        assert (
            client.get(f"/api/decisions/{second['decision_id']}").json()[
                "action_planning_status"
            ]
            == "failed"
        )

        services.planning_worker = ActionPlanningWorker(services.uow_factory)
        retried = client.post(f"/api/decisions/{second['decision_id']}/actions/retry")

        assert retried.status_code == 200
        assert retried.json()["action_planning_status"] == "complete"
        assert (
            client.get(f"/api/decisions/{first['decision_id']}").json()[
                "action_planning_status"
            ]
            == "pending"
        )
        assert client.get(f"/api/decisions/{first['decision_id']}/actions").json() == []
        assert (
            len(client.get(f"/api/decisions/{second['decision_id']}/actions").json())
            == 5
        )


@pytest.mark.parametrize(
    "identity_update",
    [
        {"effective_roles": ("material_planner",)},
        {"persona_id": "RL-PERSONA-IMPOSTOR"},
    ],
)
def test_planning_retry_requires_server_owned_response_approver(
    tmp_path,
    identity_update,
):
    def fail_planning(decision):
        del decision
        raise RuntimeError("internal planning detail")

    api = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'authorized-retry.db'}",
        ),
        planner=fail_planning,
        clock=lambda: datetime.now(UTC),
    )
    with TestClient(api) as client:
        case_id, analysis = create_and_analyze(client)
        decision = approve(client, case_id, analysis["analysis_id"]).json()
        services = api.state.services
        assert services.planning_worker.process_next_outbox() is True
        services.identity = services.identity.model_copy(update=identity_update)

        forbidden = client.post(
            f"/api/decisions/{decision['decision_id']}/actions/retry"
        )

        assert forbidden.status_code == 403
        assert forbidden.json()["detail"] == {
            "code": "ROLE_REQUIRED",
            "role": "response_approver",
        }


def test_planning_retry_rejects_caller_owned_identity_snapshot(tmp_path):
    def fail_planning(decision):
        del decision
        raise RuntimeError("internal planning detail")

    api = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'retry-body.db'}",
        ),
        planner=fail_planning,
        clock=lambda: datetime.now(UTC),
    )
    with TestClient(api) as client:
        case_id, analysis = create_and_analyze(client)
        decision = approve(client, case_id, analysis["analysis_id"]).json()
        assert api.state.services.planning_worker.process_next_outbox() is True

        response = client.post(
            f"/api/decisions/{decision['decision_id']}/actions/retry",
            json={"identity": {"effective_roles": ["response_approver"]}},
        )

        assert response.status_code == 422


def test_playback_requires_an_explicit_authorized_server_identity(client, services):
    case_id, analysis = create_and_analyze(client)
    decision = approve(client, case_id, analysis["analysis_id"]).json()
    services.run_worker_until_idle()
    services.identity = services.identity.model_copy(
        update={"effective_roles": ("material_planner",)}
    )

    response = client.post(f"/api/decisions/{decision['decision_id']}/playback")

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "ROLE_REQUIRED",
        "role": "response_approver",
    }


def test_api_responses_expose_runtime_scenario_and_source_timestamps(
    client,
    services,
    immediate_clock,
):
    case_id, analysis = create_and_analyze(client)
    approved = approve(client, case_id, analysis["analysis_id"])
    decision = approved.json()
    services.run_worker_until_idle()
    actions = client.get(f"/api/decisions/{decision['decision_id']}/actions").json()
    playback = client.post(f"/api/decisions/{decision['decision_id']}/playback").json()
    services.playback_service.run_to_completion(
        playback["playback_id"],
        clock=immediate_clock,
    )
    observations = client.get(
        f"/api/decisions/{decision['decision_id']}/observations"
    ).json()

    assert analysis["runtime_mode"] == "fallback"
    assert analysis["scenario_effective_time"]
    assert analysis["created_at"]
    assert all(item["source_timestamp"] for item in analysis["evidence_items"])
    assert all(item["retrieved_at"] for item in analysis["evidence_items"])
    case = client.get(f"/api/cases/{case_id}").json()
    assert case["recorded_at"].endswith("Z")
    assert case["projection_updated_at"].endswith("Z")
    assert decision["runtime_mode"] == "fallback"
    assert decision["analysis_material_hash"] == analysis["material_hash"]
    assert decision["calculation_version"] == "rl001-options-v1"
    assert decision["evidence_policy_version"] == "evidence-policy-v3"
    assert decision["approval_policy_version"] == "standing-authorization-v1"
    assert decision["ranking_policy_version"] == "thresholded-lexicographic-v1"
    assert {item["role"] for item in decision["approval_satisfactions"]} == {
        "finance_approver",
        "material_planner",
    }
    assert decision["scenario_effective_time"]
    assert decision["projection_updated_at"].endswith("Z")
    assert all(item["projection_updated_at"].endswith("Z") for item in actions)
    assert all(item["runtime_mode"] == "fallback" for item in observations)
    assert all(item["recorded_at"] for item in observations)


def test_dashboard_cases_reports_persisted_projection_timestamps(client, services):
    case_id, analysis = create_and_analyze(client, purpose="showcase")
    approved = approve(client, case_id, analysis["analysis_id"])
    services.run_worker_until_idle()

    response = client.get("/api/dashboard/cases")

    assert response.status_code == 200
    item = next(row for row in response.json() if row["case_id"] == case_id)
    assert item["runtime_mode"] == "fallback"
    assert item["scenario_effective_time"]
    assert item["projection_updated_at"]
    assert item["analysis_created_at"] == analysis["created_at"]
    assert item["decision_decided_at"] == approved.json()["decided_at"]
    assert item["recommended_option_id"] == "RL-OPTION-COMBINED"
    assert item["selected_option_id"] == "RL-OPTION-COMBINED"
    assert item["action_count"] == 5


def test_analysis_runs_through_the_startup_composed_service(client, services):
    created = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": "automated_test"},
    )
    case_id = created.json()["case_id"]
    composed = services.analysis_service
    calls = []

    class RecordingAnalysisService:  # allowed - composition wiring test double
        def create(self, requested_case_id):
            calls.append(requested_case_id)
            return composed.create(requested_case_id)

    services.analysis_service = RecordingAnalysisService()

    response = client.post(f"/api/cases/{case_id}/analysis")

    assert response.status_code == 201
    assert calls == [case_id]
    assert response.json()["recommendation"]["option_id"] == "RL-OPTION-COMBINED"
