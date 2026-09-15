from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.execution.playback import ImmediateClock


def _wait_for_json(client, path, predicate, *, timeout=1.0):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200
        latest = response.json()
        if predicate(latest):
            return latest
        time.sleep(0.01)
    raise AssertionError(f"condition not reached for {path}: {latest}")


def _create_and_approve(client):
    created = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": "automated_test"},
    )
    assert created.status_code == 201
    case_id = created.json()["case_id"]
    analysis = client.post(f"/api/cases/{case_id}/analysis")
    assert analysis.status_code == 201
    approved = client.post(
        f"/api/cases/{case_id}/decisions",
        headers={"Idempotency-Key": f"RL-RUNTIME-{case_id}"},
        json={
            "analysis_id": analysis.json()["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )
    assert approved.status_code == 201
    return case_id, approved.json()


def test_lifespan_advances_pending_decision_to_five_actions_and_unsent_draft(
    client,
):
    _, approved = _create_and_approve(client)

    assert approved["action_planning_status"] == "pending"
    decision_id = approved["decision_id"]
    completed = _wait_for_json(
        client,
        f"/api/decisions/{decision_id}",
        lambda item: item["action_planning_status"] != "pending",
    )
    actions = client.get(f"/api/decisions/{decision_id}/actions").json()
    drafts = client.get(f"/api/decisions/{decision_id}/drafts").json()

    assert completed["action_planning_status"] == "complete"
    assert len(actions) == 5
    assert len(drafts) == 1
    assert drafts[0]["sent"] is False


def test_lifespan_completes_explicit_playback_without_blocking_or_duplicates(
    client,
):
    _, approved = _create_and_approve(client)
    decision_id = approved["decision_id"]
    _wait_for_json(
        client,
        f"/api/decisions/{decision_id}",
        lambda item: item["action_planning_status"] == "complete",
    )

    started_at = time.monotonic()
    started = client.post(f"/api/decisions/{decision_id}/playback")
    elapsed = time.monotonic() - started_at
    repeated = client.post(f"/api/decisions/{decision_id}/playback")

    assert started.status_code == repeated.status_code == 201
    assert elapsed < 0.2
    assert repeated.json()["playback_id"] == started.json()["playback_id"]
    completed = _wait_for_json(
        client,
        f"/api/decisions/{decision_id}/playback",
        lambda item: item["status"] == "completed",
    )
    observations = client.get(f"/api/decisions/{decision_id}/observations").json()

    assert completed["completed_at"] is not None
    assert len(observations) == 5
    assert {item["display_label"] for item in observations} == {"Simulated"}
    assert len({item["observation_id"] for item in observations}) == 5


def test_lifespan_does_not_globally_retry_failed_planning(tmp_path):
    calls = 0

    def fail_planning(decision, analysis):
        nonlocal calls
        del decision, analysis
        calls += 1
        raise RuntimeError("planner failed")

    immediate = ImmediateClock(datetime.now(UTC))
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'failed-runtime.db'}",
        ),
        clock=immediate.now,
        playback_clock=immediate,
        planner=fail_planning,
    )
    with TestClient(app) as client:
        _, approved = _create_and_approve(client)
        decision_id = approved["decision_id"]
        failed = _wait_for_json(
            client,
            f"/api/decisions/{decision_id}",
            lambda item: item["action_planning_status"] == "failed",
        )
        time.sleep(0.1)

        assert failed["action_planning_status"] == "failed"
        assert calls == 1


def test_lifespan_recovers_persisted_in_progress_playback_after_restart(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'playback-restart.db'}"
    first_clock = ImmediateClock(datetime.now(UTC))
    first_app = create_app(
        Settings(runtime_mode=RuntimeMode.FALLBACK, database_url=database_url),
        clock=first_clock.now,
        playback_clock=first_clock,
    )
    with TestClient(first_app) as first:
        _, approved = _create_and_approve(first)
        decision_id = approved["decision_id"]
        _wait_for_json(
            first,
            f"/api/decisions/{decision_id}",
            lambda item: item["action_planning_status"] == "complete",
        )

    playback = first_app.state.services.playback_service.start(
        decision_id,
        first_app.state.services.identity,
    )
    restarted_clock = ImmediateClock(datetime.now(UTC))
    restarted_app = create_app(
        Settings(runtime_mode=RuntimeMode.FALLBACK, database_url=database_url),
        clock=restarted_clock.now,
        playback_clock=restarted_clock,
    )
    with TestClient(restarted_app) as restarted:
        completed = _wait_for_json(
            restarted,
            f"/api/decisions/{decision_id}/playback",
            lambda item: item["status"] == "completed",
        )

    assert completed["playback_id"] == playback.playback_id


def test_playback_worker_retries_transient_failure_and_recovers(tmp_path):
    clock = ImmediateClock(datetime.now(UTC))
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'playback-transient.db'}",
        ),
        clock=clock.now,
        playback_clock=clock,
    )
    attempts = 0
    original = app.state.services.playback_service.run_to_completion

    def transient(playback_id):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("transient playback fault")
        return original(playback_id)

    app.state.services.playback_service.run_to_completion = transient
    with TestClient(app) as client:
        _, approved = _create_and_approve(client)
        decision_id = approved["decision_id"]
        _wait_for_json(
            client,
            f"/api/decisions/{decision_id}",
            lambda item: item["action_planning_status"] == "complete",
        )
        client.post(f"/api/decisions/{decision_id}/playback")
        completed = _wait_for_json(
            client,
            f"/api/decisions/{decision_id}/playback",
            lambda item: item["status"] == "completed",
            timeout=2,
        )

    assert completed["error_code"] is None
    assert attempts == 3


def test_playback_worker_records_bounded_terminal_failure(tmp_path):
    clock = ImmediateClock(datetime.now(UTC))
    app = create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'playback-terminal.db'}",
        ),
        clock=clock.now,
        playback_clock=clock,
    )

    def always_fail(playback_id):
        del playback_id
        raise RuntimeError("secret internal playback failure detail")

    app.state.services.playback_service.run_to_completion = always_fail
    with TestClient(app) as client:
        _, approved = _create_and_approve(client)
        decision_id = approved["decision_id"]
        _wait_for_json(
            client,
            f"/api/decisions/{decision_id}",
            lambda item: item["action_planning_status"] == "complete",
        )
        client.post(f"/api/decisions/{decision_id}/playback")
        failed = _wait_for_json(
            client,
            f"/api/decisions/{decision_id}/playback",
            lambda item: item["status"] == "failed",
            timeout=2,
        )

    assert failed["error_code"] == "PLAYBACK_EXECUTION_FAILED"
    assert failed["completed_at"] is None
    assert "secret" not in str(failed).lower()
