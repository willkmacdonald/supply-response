import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

from apps.api.app.dependencies import get_actor, require_planner
from data.domain import RuntimeMode
from data.domain import cases as case_domain


def test_inbox_unavailable_in_fallback(client):
    response = client.post("/api/inbox/check", json={})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "INBOX_CHECK_UNAVAILABLE"


def setup_inbox(app, services):
    services.settings = services.settings.model_copy(
        update={
            "runtime_mode": RuntimeMode.LIVE,
            "entra_client_secret": "fixture-presenter-receipt-secret",
        }
    )
    actor = SimpleNamespace(tenant_id="tenant-a", object_id="actor-a")
    app.dependency_overrides[require_planner] = lambda: actor
    app.dependency_overrides[get_actor] = lambda: actor
    services.inbox_service = SimpleNamespace(
        check_inbox=AsyncMock(
            return_value={
                "checked_at": "2026-09-14T05:00:00Z",
                "messages": [],
                "incomplete": False,
            }
        )
    )
    return actor


def test_inbox_delegates_actor_and_does_not_create_cases(app, client, services):
    actor = setup_inbox(app, services)
    response = client.post("/api/inbox/check", json={})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    services.inbox_service.check_inbox.assert_awaited_once_with(
        actor=actor, checked_at=services.clock()
    )
    assert response.json()["messages"] == []


def test_successive_checks_mint_distinct_presenter_runs(app, client, services):
    setup_inbox(app, services)
    first = client.post("/api/inbox/check", json={})
    second = client.post("/api/inbox/check", json={})
    assert first.status_code == second.status_code == 200
    assert re.fullmatch(
        case_domain.PRESENTER_RUN_PATTERN, first.json()["presenter_run_id"]
    )
    assert first.json()["presenter_run_id"] != second.json()["presenter_run_id"]
    assert first.json()["presenter_run_receipt"]
    assert (
        first.json()["presenter_run_receipt"] != second.json()["presenter_run_receipt"]
    )


def test_inbox_failure_does_not_leak_raw_errors(app, client, services):
    setup_inbox(app, services)
    services.inbox_service.check_inbox.side_effect = RuntimeError("secret token")
    response = client.post("/api/inbox/check", json={})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "INBOX_CHECK_FAILED"
    assert "secret" not in response.text
    assert "presenter_run_id" not in response.text
    assert "presenter_run_receipt" not in response.text


def test_inbox_rejects_client_supplied_scope(app, client, services):
    setup_inbox(app, services)
    response = client.post("/api/inbox/check", json={"mailbox": "other@example.com"})
    assert response.status_code == 422
    services.inbox_service.check_inbox.assert_not_awaited()


def test_inbox_requires_authentication(app, client, services):
    setup_inbox(app, services)
    app.dependency_overrides[require_planner] = lambda: None
    response = client.post("/api/inbox/check", json={})
    assert response.status_code == 401
    services.inbox_service.check_inbox.assert_not_awaited()


def test_inbox_enforces_actual_planner_guard(app, client, services):
    setup_inbox(app, services)
    del app.dependency_overrides[require_planner]
    services.settings = services.settings.model_copy(
        update={
            "allowed_tenant_id": "9492545f-58bd-4fe2-974e-7124c38e4c2b",
            "alex_object_id": "00000000-0000-0000-0000-000000000001",
        }
    )
    app.dependency_overrides[get_actor] = lambda: SimpleNamespace(
        tenant_id=services.settings.allowed_tenant_id,
        object_id="00000000-0000-0000-0000-000000000002",
        persona_id="RL-PERSONA-TAYLOR",
        source_id="RL-ENTRA-TAYLOR",
        effective_roles=("finance_approver",),
    )
    assert client.post("/api/inbox/check", json={}).status_code == 403
    services.inbox_service.check_inbox.assert_not_awaited()
