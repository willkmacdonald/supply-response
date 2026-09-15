from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.api.app.dependencies import get_actor, require_planner
from data.domain import RuntimeMode
from data.domain.inbound import InboundEmailError
from data.synthetic.rl001 import instantiate_rl001
from services.persistence.sqlite import sqlite_store
from services.persistence.store import ImmutableRecordConflict
from tests.integration.test_workiq_contract import _authenticated_alex
from tests.persistence.test_inbound_binding import source


def setup(app, services, tmp_path):
    _, actor = _authenticated_alex()
    app.dependency_overrides[require_planner] = lambda: actor
    app.dependency_overrides[get_actor] = lambda: actor
    services.settings = services.settings.model_copy(
        update={"runtime_mode": RuntimeMode.LIVE, "independent_finance_enabled": True}
    )
    services.store = sqlite_store(
        f"sqlite:///{tmp_path / 'inbound.db'}", runtime_mode=RuntimeMode.LIVE
    )
    bound = source().model_copy(
        update={"tenant_id": actor.tenant_id, "mailbox_object_id": actor.object_id}
    )
    services.inbox_service = SimpleNamespace(
        review_inbound_email=AsyncMock(return_value=bound)
    )

    async def retrieve(**kwargs):
        case, snapshot = instantiate_rl001(
            case_id=kwargs["case_id"],
            purpose=kwargs["purpose"],
            runtime_mode=RuntimeMode.LIVE,
        )
        return SimpleNamespace(case=case, snapshot=snapshot)

    services.live_operational_data = SimpleNamespace(
        retrieve=AsyncMock(side_effect=retrieve)
    )
    return (
        actor,
        bound,
        {
            "presenter_run_id": "RL-RUN-" + "a" * 32,
            "internet_message_id": bound.internet_message_id,
            "review_fingerprint": bound.review_fingerprint,
        },
    )


def test_create_rechecks_source_binds_case_and_retry_returns_same_open_case(
    app, client, services, tmp_path
):
    actor, bound, payload = setup(app, services, tmp_path)
    first = client.post("/api/inbox/cases", json=payload)
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    body = first.json()
    assert body["status"] == "open" and body["current_analysis_id"] is None
    assert body["workflow_version"] == "independent-finance-v1"
    assert body.get("supplier_email", {}).get("sender") == bound.sender
    assert body["supplier_email"][
        "received_at"
    ] == bound.received_at.isoformat().replace("+00:00", "Z")
    assert services.store.get_case(body["case_id"]).supplier_email == bound
    services.inbox_service.review_inbound_email.assert_awaited_once_with(
        actor=actor,
        checked_at=services.clock(),
        internet_message_id=payload["internet_message_id"],
        review_fingerprint=payload["review_fingerprint"],
    )
    # Current provider locator can change while the reviewed source identity stays fixed.
    services.inbox_service.review_inbound_email.return_value = bound.model_copy(
        update={"message_id": "moved"}
    )
    second = client.post("/api/inbox/cases", json=payload)
    assert second.status_code == 200 and second.json()["case_id"] == body["case_id"]
    assert services.live_operational_data.retrieve.await_count == 1


def test_same_email_is_fresh_across_runs_and_idempotent_within_run(
    app, client, services, tmp_path
):
    _, _, payload = setup(app, services, tmp_path)
    run_a = {**payload, "presenter_run_id": "RL-RUN-" + "a" * 32}
    run_b = {**payload, "presenter_run_id": "RL-RUN-" + "b" * 32}
    first = client.post("/api/inbox/cases", json=run_a)
    retry = client.post("/api/inbox/cases", json=run_a)
    second = client.post("/api/inbox/cases", json=run_b)
    assert first.status_code == retry.status_code == second.status_code == 200
    assert retry.json()["case_id"] == first.json()["case_id"]
    assert second.json()["case_id"] != first.json()["case_id"]
    assert second.json()["presenter_run_id"] == run_b["presenter_run_id"]
    assert second.json()["current_analysis_id"] is None
    assert second.json()["current_decision_id"] is None
    assert second.json()["status"] == "open"


@pytest.mark.parametrize(
    "change,code,status",
    [
        ("fingerprint", "INBOUND_EMAIL_CHANGED", 409),
        ("facts", "INBOUND_EMAIL_CONFLICT", 409),
        ("scope", "INBOUND_EMAIL_CONFLICT", 409),
        ("unsupported", "INBOUND_EMAIL_UNSUPPORTED", 422),
        ("provider", "INBOUND_EMAIL_UNAVAILABLE", 503),
    ],
)
def test_invalid_source_fails_without_orphan(
    app, client, services, tmp_path, change, code, status
):
    _, bound, payload = setup(app, services, tmp_path)
    if change == "fingerprint":
        services.inbox_service.review_inbound_email.return_value = bound.model_copy(
            update={"review_fingerprint": "b" * 64}
        )
    elif change == "facts":
        services.inbox_service.review_inbound_email.return_value = bound.model_copy(
            update={"facts": bound.facts.model_copy(update={"original_quantity": 9000})}
        )
    elif change == "scope":
        services.inbox_service.review_inbound_email.return_value = bound.model_copy(
            update={"mailbox_object_id": "other"}
        )
    else:
        services.inbox_service.review_inbound_email.side_effect = (
            InboundEmailError(code)
            if change == "unsupported"
            else RuntimeError("secret provider payload")
        )
    result = client.post("/api/inbox/cases", json=payload)
    assert result.status_code == status
    assert result.json()["detail"]["code"] == code
    assert result.headers["cache-control"] == "no-store" and "secret" not in result.text
    assert services.store.list_cases() == ()


def test_same_identity_with_new_fingerprint_conflicts(app, client, services, tmp_path):
    _, bound, payload = setup(app, services, tmp_path)
    assert client.post("/api/inbox/cases", json=payload).status_code == 200
    services.inbox_service.review_inbound_email.return_value = bound.model_copy(
        update={"review_fingerprint": "b" * 64}
    )
    result = client.post(
        "/api/inbox/cases", json={**payload, "review_fingerprint": "b" * 64}
    )
    assert result.status_code == 409
    assert len(services.store.list_cases()) == 1


def test_concurrent_primary_key_winner_is_validated_and_returned(
    app, client, services, tmp_path, monkeypatch
):
    _, _, payload = setup(app, services, tmp_path)
    create = services.store.create_presenter_case

    def concurrent(case, snapshot):
        create(case, snapshot)
        raise ImmutableRecordConflict("winner")

    monkeypatch.setattr(services.store, "create_presenter_case", concurrent)
    result = client.post("/api/inbox/cases", json=payload)
    assert result.status_code == 200, result.text
    assert len(services.store.list_cases()) == 1


def test_authentication_live_gate_and_untrusted_request_fields(
    app, client, services, tmp_path
):
    assert (
        client.post(
            "/api/inbox/cases",
            json={
                "presenter_run_id": "RL-RUN-" + "a" * 32,
                "internet_message_id": "<a@b>",
                "review_fingerprint": "a" * 64,
            },
        ).status_code
        == 503
    )
    _, _, payload = setup(app, services, tmp_path)
    for invalid in (
        {key: value for key, value in payload.items() if key != "presenter_run_id"},
        {**payload, "presenter_run_id": "client-selected-run"},
    ):
        result = client.post("/api/inbox/cases", json=invalid)
        assert result.status_code == 422
        assert result.json()["detail"]["code"] == "INVALID_INBOUND_REQUEST"
        assert result.headers.get("cache-control") == "no-store"
    for key in ("body", "facts", "mailbox", "sender", "case_id"):
        result = client.post("/api/inbox/cases", json={**payload, key: "untrusted"})
        assert result.status_code == 422
        assert result.json()["detail"]["code"] == "INVALID_INBOUND_REQUEST"
        assert result.headers.get("cache-control") == "no-store"
    app.dependency_overrides[require_planner] = lambda: None
    assert client.post("/api/inbox/cases", json=payload).status_code == 401
    services.inbox_service.review_inbound_email.assert_not_awaited()


def test_actual_planner_guard_and_no_store_for_forbidden_actor(
    app, client, services, tmp_path
):
    actor, _, payload = setup(app, services, tmp_path)
    del app.dependency_overrides[require_planner]
    services.settings = services.settings.model_copy(
        update={"allowed_tenant_id": actor.tenant_id, "alex_object_id": actor.object_id}
    )
    app.dependency_overrides[get_actor] = lambda: SimpleNamespace(
        tenant_id=actor.tenant_id,
        object_id="other",
        persona_id="RL-PERSONA-TAYLOR",
        source_id="RL-ENTRA-TAYLOR",
        effective_roles=("finance_approver",),
    )
    result = client.post("/api/inbox/cases", json=payload)
    assert result.status_code == 403
    assert result.headers.get("cache-control") == "no-store"
    services.inbox_service.review_inbound_email.assert_not_awaited()


@pytest.mark.anyio
async def test_actual_concurrent_requests_return_one_atomic_case(
    app, services, tmp_path
):
    import asyncio

    from fastapi import Response

    from apps.api.app.routes.inbox import CreateInboundCaseRequest, create_inbound_case

    actor, _, payload = setup(app, services, tmp_path)
    original = services.live_operational_data.retrieve.side_effect
    barrier = asyncio.Barrier(2)

    async def overlapping(**kwargs):
        await barrier.wait()
        return await original(**kwargs)

    services.live_operational_data.retrieve.side_effect = overlapping
    results = await asyncio.gather(
        *(
            create_inbound_case(
                CreateInboundCaseRequest(**payload), Response(), services, actor
            )
            for _ in range(2)
        )
    )
    assert results[0].case_id == results[1].case_id
    assert len(services.store.list_cases()) == 1


def test_conflicting_concurrent_winner_is_not_returned(
    app, client, services, tmp_path, monkeypatch
):
    from data.domain import CaseInstance

    _, _, payload = setup(app, services, tmp_path)
    create = services.store.create_presenter_case

    def concurrent(case, snapshot):
        changed = CaseInstance.model_validate(
            {
                **case.model_dump(),
                "supplier_email": case.supplier_email.model_copy(
                    update={"review_fingerprint": "b" * 64}
                ),
            }
        )
        create(changed, snapshot)
        raise ImmutableRecordConflict("winner")

    monkeypatch.setattr(services.store, "create_presenter_case", concurrent)
    result = client.post("/api/inbox/cases", json=payload)
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "INBOUND_EMAIL_CHANGED"


def test_inbound_creation_retains_four_runs(app, client, services, tmp_path):
    _, _, payload = setup(app, services, tmp_path)
    created = []
    for index in range(5):
        response = client.post(
            "/api/inbox/cases",
            json={**payload, "presenter_run_id": f"RL-RUN-{index:032x}"},
        )
        assert response.status_code == 200, response.text
        created.append(response.json()["case_id"])
    retained = {case.case_id for case in services.store.list_cases()}
    assert len(retained) == 4
    assert created[-1] in retained


def test_failed_new_run_analysis_preserves_fresh_case_and_earlier_decision(
    app, client, services, tmp_path
):
    from agents.orchestrator.local import LocalAgentSet
    from agents.orchestrator.workflow import Orchestrator
    from apps.api.app.live import LiveAnalysisApplicationService
    from services.analysis.service import analyze_case
    from services.decisions.service import DecisionService
    from tests.integration.test_inbound_analysis import BoundWorkIQ
    from tests.integration.test_live_case_contract import NOW
    from tests.integration.test_live_hardening import ExplicitLiveOperationalPort

    _, bound, payload = setup(app, services, tmp_path)
    # A retained legacy workflow Case can already have a completed Decision.
    services.settings = services.settings.model_copy(
        update={"independent_finance_enabled": False}
    )
    workiq = BoundWorkIQ()
    services.analysis_service = LiveAnalysisApplicationService(
        store=services.store,
        operational_data=ExplicitLiveOperationalPort(),
        work_iq=workiq,
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="seed-locator",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: NOW,
    )
    services.decision_service = DecisionService(services.uow_factory, clock=lambda: NOW)
    first = client.post("/api/inbox/cases", json=payload)
    assert first.status_code == 200, first.text
    first_id = first.json()["case_id"]
    analyzed = client.post(f"/api/cases/{first_id}/analysis")
    assert analyzed.status_code == 201, analyzed.text
    approved = client.post(
        f"/api/cases/{first_id}/decisions",
        headers={"Idempotency-Key": "earlier-run"},
        json={
            "analysis_id": analyzed.json()["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )
    assert approved.status_code == 201, approved.text
    decision_id = approved.json()["decision_id"]
    services.settings = services.settings.model_copy(
        update={"independent_finance_enabled": True}
    )
    second_payload = {**payload, "presenter_run_id": "RL-RUN-" + "b" * 32}
    second = client.post("/api/inbox/cases", json=second_payload)
    assert second.status_code == 200, second.text
    second_id = second.json()["case_id"]
    assert second_id != first_id
    for body in (second.json(),):
        assert body["status"] == "open"
        assert body["current_analysis_id"] is None
        assert body["current_decision_id"] is None
    workiq.fail = True
    failed = client.post(f"/api/cases/{second_id}/analysis")
    assert failed.status_code == 503, failed.text
    for response in (
        client.get(f"/api/cases/{second_id}"),
        client.post("/api/inbox/cases", json=second_payload),
    ):
        assert response.status_code == 200, response.text
        assert response.json()["case_id"] == second_id
        assert response.json()["status"] == "open"
        assert response.json()["current_analysis_id"] is None
        assert response.json()["current_decision_id"] is None
    assert services.store.get_case(second_id).supplier_email == bound
    earlier = client.get(f"/api/cases/{first_id}").json()
    assert earlier["current_decision_id"] == decision_id
    assert earlier["current_analysis_id"] == analyzed.json()["analysis_id"]
    assert client.get(f"/api/decisions/{decision_id}").json()["case_id"] == first_id
    with services.uow_factory() as uow:
        assert tuple(
            item.decision_id for item in uow.decisions.list_for_case(first_id)
        ) == (decision_id,)
        assert uow.decisions.list_for_case(second_id) == ()
