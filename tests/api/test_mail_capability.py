from types import SimpleNamespace
from unittest.mock import AsyncMock

from apps.api.app.dependencies import get_actor, require_planner
from data.domain import RuntimeMode
from integrations.graph_mail.client import GraphMailCapability, GraphMailError


def _configure_live_capability(app, services):
    services.settings = services.settings.model_copy(
        update={"runtime_mode": RuntimeMode.LIVE}
    )
    actor = SimpleNamespace(tenant_id="tenant-a", object_id="alex-a")
    graph = SimpleNamespace(
        capability=AsyncMock(
            return_value=GraphMailCapability(
                mailbox_address="agent@willmacdonald.com",
                sample_sent_message_id="provider-message-id-must-not-leak",
            )
        )
    )
    services.graph_mail = graph
    app.dependency_overrides[require_planner] = lambda: actor
    app.dependency_overrides[get_actor] = lambda: actor
    return actor, graph


def test_mail_capability_is_unavailable_without_graph(app, client):
    app.dependency_overrides[require_planner] = lambda: SimpleNamespace(
        tenant_id="tenant-a", object_id="alex-a"
    )
    response = client.get("/api/supplier-email/capability")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "SUPPLIER_EMAIL_CAPABILITY_UNAVAILABLE",
        "message": "Mailbox verification is not available.",
    }


def test_mail_capability_requires_authenticated_alex(app, client, services):
    _, graph = _configure_live_capability(app, services)
    app.dependency_overrides[require_planner] = lambda: None

    response = client.get("/api/supplier-email/capability")

    assert response.status_code == 401
    assert response.json()["detail"] == {"code": "AUTHENTICATION_REQUIRED"}
    graph.capability.assert_not_awaited()


def test_mail_capability_returns_only_safe_verification(app, client, services):
    actor, graph = _configure_live_capability(app, services)

    response = client.get("/api/supplier-email/capability")

    assert response.status_code == 200
    assert response.json() == {
        "mailbox_address": "agent@willmacdonald.com",
        "sample_sent_message_verified": True,
    }
    graph.capability.assert_awaited_once_with(actor)
    assert "provider-message-id" not in response.text


def test_mail_capability_hides_provider_failure(app, client, services):
    _, graph = _configure_live_capability(app, services)
    graph.capability.side_effect = GraphMailError("graph_capability_failed")

    response = client.get("/api/supplier-email/capability")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "SUPPLIER_EMAIL_CAPABILITY_FAILED",
        "message": "Mailbox verification could not be completed.",
    }
    assert "graph" not in response.text.lower()


def test_mail_capability_enforces_actual_alex_guard(app, client, services):
    _, graph = _configure_live_capability(app, services)
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

    response = client.get("/api/supplier-email/capability")

    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "PLANNER_ACCESS_REQUIRED"}
    graph.capability.assert_not_awaited()
