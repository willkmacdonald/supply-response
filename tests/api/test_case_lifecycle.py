def test_fallback_case_runs_from_creation_through_observations(
    client,
    services,
    immediate_clock,
):
    created = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": "automated_test"},
    )

    assert created.status_code == 201
    case_id = created.json()["case_id"]
    analysis = client.post(f"/api/cases/{case_id}/analysis").json()
    assert analysis["recommendation"]["option_id"] == "RL-OPTION-COMBINED"

    decision_response = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": "RL-API-DECISION-1"},
        json={
            "analysis_id": analysis["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )
    assert decision_response.status_code == 201
    decision = decision_response.json()
    services.run_worker_until_idle()
    actions = client.get(f"/api/decisions/{decision['decision_id']}/actions").json()
    assert len(actions) == 5

    playback_response = client.post(
        f"/api/decisions/{decision['decision_id']}/playback"
    )
    assert playback_response.status_code == 201
    playback = playback_response.json()
    services.playback_service.run_to_completion(
        playback["playback_id"],
        clock=immediate_clock,
    )
    repeated_playback = client.post(
        f"/api/decisions/{decision['decision_id']}/playback"
    )
    drafts = client.get(f"/api/decisions/{decision['decision_id']}/drafts").json()
    observations = client.get(
        f"/api/decisions/{decision['decision_id']}/observations"
    ).json()
    assert repeated_playback.json()["playback_id"] == playback["playback_id"]
    assert len(drafts) == 1
    assert drafts[0]["sent"] is False
    assert drafts[0]["subject"] == "RL-001 recovery-date confirmation request"
    assert len(observations) == 10
    assert {item["display_label"] for item in observations} == {"Simulated"}


def test_closed_loop_state_survives_application_restart(tmp_path, immediate_clock):
    from fastapi.testclient import TestClient

    from apps.api.app.main import create_app
    from apps.api.app.settings import Settings
    from data.domain import RuntimeMode

    settings = Settings(
        runtime_mode=RuntimeMode.FALLBACK,
        database_url=f"sqlite:///{tmp_path / 'restart.db'}",
    )
    first_app = create_app(
        settings,
        clock=immediate_clock.now,
        playback_clock=immediate_clock,
    )
    with TestClient(first_app) as first:
        case_id = first.post(
            "/api/cases",
            json={"template_id": "RL-001", "purpose": "automated_test"},
        ).json()["case_id"]
        analysis = first.post(f"/api/cases/{case_id}/analysis").json()
        decision = first.post(
            f"/api/cases/{case_id}/decisions",
            headers={"Idempotency-Key": "RL-API-RESTART"},
            json={
                "analysis_id": analysis["analysis_id"],
                "kind": "approved",
                "selected_option_id": "RL-OPTION-COMBINED",
            },
        ).json()

    restarted_app = create_app(
        settings,
        clock=immediate_clock.now,
        playback_clock=immediate_clock,
    )
    with TestClient(restarted_app) as restarted:
        restarted_app.state.services.run_worker_until_idle()
        persisted = restarted.get(f"/api/cases/{case_id}")
        actions = restarted.get(f"/api/decisions/{decision['decision_id']}/actions")

    assert persisted.status_code == 200
    assert persisted.json()["current_decision_id"] == decision["decision_id"]
    assert len(actions.json()) == 5
