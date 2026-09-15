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
        update={
            "runtime_mode": RuntimeMode.LIVE,
            "independent_finance_enabled": True,
        }
    )
    services.store = sqlite_store(
        f"sqlite:///{tmp_path / 'inbound.db'}", runtime_mode=RuntimeMode.LIVE
    )
    bound = source().model_copy(
        update={"tenant_id": actor.tenant_id, "mailbox_object_id": actor.object_id}
    )
    services.inbox_service = SimpleNamespace(
        check_inbox=AsyncMock(
            return_value={
                "checked_at": "2026-09-14T05:00:00Z",
                "messages": [
                    {
                        "message_id": bound.message_id,
                        "subject": bound.subject,
                        "sender": bound.sender,
                        "received_at": bound.received_at,
                        "excerpt": "Supplier disruption",
                        "citation_url": bound.citation_url,
                        "internet_message_id": bound.internet_message_id,
                        "review_fingerprint": bound.review_fingerprint,
                        "facts": bound.facts,
                        "creation_blocker": None,
                    }
                ],
                "incomplete": False,
            }
        ),
        review_inbound_email=AsyncMock(return_value=bound),
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
    presenter_run_id = "RL-RUN-" + "a" * 32
    return (
        actor,
        bound,
        presenter_payload(bound, presenter_run_id),
    )


def presenter_payload(bound, presenter_run_id):
    return {
        "presenter_run_id": presenter_run_id,
        "internet_message_id": bound.internet_message_id,
        "review_fingerprint": bound.review_fingerprint,
    }


def issued_payload(client, bound):
    checked = client.post("/api/inbox/check", json={})
    assert checked.status_code == 200, checked.text
    return {
        "presenter_run_id": checked.json()["presenter_run_id"],
        "internet_message_id": bound.internet_message_id,
        "review_fingerprint": bound.review_fingerprint,
    }


def seed_complete_earlier_run(
    store, case_id, analysis_id, authenticated_alex, playback_service
):
    from collections.abc import Callable
    from datetime import datetime, timedelta
    from typing import cast
    from uuid import UUID

    from data.domain.cases import WorkflowVersion
    from data.domain.decisions import DecisionKind, IdentitySnapshot
    from data.domain.evidence import IdentitySource
    from services.execution.playback import ImmediateClock
    from services.execution.worker import ActionPlanningWorker
    from services.finance.contracts import (
        FinalizeProposalCommand,
        ResolveFinanceCommand,
        SubmitProposalCommand,
    )
    from services.finance.decisions import FinanceDecisionService
    from services.finance.identity import BoundFinanceActors
    from services.finance.service import FinanceService
    from services.persistence.ports import UnitOfWork

    started = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    taylor_object_id = "33333333-3333-4333-8333-333333333333"
    actors = BoundFinanceActors(
        tenant_id=UUID(authenticated_alex.tenant_id),
        alex_object_id=UUID(authenticated_alex.object_id),
        taylor_object_id=UUID(taylor_object_id),
    )
    alex = IdentitySnapshot(
        persona_id=authenticated_alex.persona_id,
        source_id=authenticated_alex.source_id,
        identity_source=IdentitySource.ENTRA,
        tenant_id=authenticated_alex.tenant_id,
        object_id=authenticated_alex.object_id,
        effective_roles=authenticated_alex.effective_roles,
        display_name="Alex Morgan",
        user_principal_name="alex@example.invalid",
    )
    taylor = IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR",
        source_id="RL-ENTRA-TAYLOR",
        identity_source=IdentitySource.ENTRA,
        tenant_id=authenticated_alex.tenant_id,
        object_id=taylor_object_id,
        effective_roles=("finance_approver",),
        display_name="Taylor Kim",
        user_principal_name="taylor@example.invalid",
    )
    factory = cast(Callable[[], UnitOfWork], store.uow_factory)
    times = iter(started + timedelta(minutes=index) for index in range(1, 8))
    finance = FinanceService(factory, actors=actors, clock=lambda: next(times))
    with factory() as uow:
        expected = uow.proposals.get_state(case_id).token
    submitted = finance.submit(
        SubmitProposalCommand(
            case_id=case_id,
            option_id="RL-OPTION-COMBINED",
            expected=expected,
            idempotency_key="earlier-run-submit",
        ),
        alex,
    )
    assert submitted.review is not None
    assert submitted.review_revision is not None
    with factory() as uow:
        selected = uow.proposals.get_state(case_id)
    resolved = finance.resolve(
        ResolveFinanceCommand(
            review_id=submitted.review.review_id,
            expected=selected.token,
            expected_review_revision=submitted.review_revision,
            approved=True,
            reason=None,
            idempotency_key="earlier-run-taylor-approval",
        ),
        taylor,
    )
    assert resolved.review.reviewed_by == taylor
    with factory() as uow:
        approved = uow.proposals.get_state(case_id)
    decision = FinanceDecisionService(
        factory,
        actors=actors,
        clock=lambda: next(times),
    ).finalize(
        FinalizeProposalCommand(
            case_id=case_id,
            expected=approved.token,
            kind=DecisionKind.APPROVED,
            idempotency_key="earlier-run-alex-decision",
            rejection_reason=None,
        ),
        alex,
    )
    assert decision.actor == alex
    assert ActionPlanningWorker(
        factory,
        processable_workflow_versions=(WorkflowVersion.INDEPENDENT_FINANCE,),
    ).process_decision_outbox(decision.decision_id)
    playback = playback_service.start(decision.decision_id, alex)
    playback_service.run_to_completion(playback.playback_id, clock=ImmediateClock())
    return submitted.review.review_id, decision.decision_id


def saved_earlier_run_values(store, analysis_id, review_id, decision_id):
    with store.uow_factory() as uow:
        actions = uow.execution.list_actions(decision_id=decision_id)
        playback = uow.execution.get_playback_for_decision(decision_id)
        assert playback is not None
        return {
            "analysis": uow.cases.get_analysis(analysis_id),
            "finance_review": uow.finance_reviews.get_latest(review_id),
            "decision": uow.decisions.get(decision_id),
            "outbox": uow.execution.list_outbox(decision_id=decision_id),
            "actions": actions,
            "drafts": tuple(
                uow.execution.get_draft_artifact(action.action_id)
                for action in actions
                if action.draft_artifact_id is not None
            ),
            "attempts": tuple(
                (action.action_id, uow.execution.list_attempts(action.action_id))
                for action in actions
            ),
            "status_events": tuple(
                (action.action_id, uow.execution.list_status_events(action.action_id))
                for action in actions
            ),
            "playback": playback,
            "outcomes": uow.execution.list_observations(decision_id),
        }


def presenter_aggregate_counts(store, case_id):
    from services.persistence.presenter_runs import (
        PresenterRetentionPlan,
        count_presenter_aggregate_deletions,
    )

    plan = PresenterRetentionPlan(case_id, (), (case_id,))
    with store.engine.connect() as connection:
        return count_presenter_aggregate_deletions(connection, plan)


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
    _, bound, _ = setup(app, services, tmp_path)
    run_a = issued_payload(client, bound)
    run_b = issued_payload(client, bound)
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


def test_new_run_for_same_email_is_isolated_from_the_complete_earlier_run(
    app, client, services, tmp_path
):
    from agents.orchestrator.local import LocalAgentSet
    from agents.orchestrator.workflow import Orchestrator
    from apps.api.app.live import LiveAnalysisApplicationService
    from services.analysis.service import analyze_case
    from services.execution.playback import ImmediateClock, PlaybackService
    from tests.integration.test_inbound_analysis import BoundWorkIQ
    from tests.integration.test_live_case_contract import NOW
    from tests.integration.test_live_hardening import ExplicitLiveOperationalPort

    actor, bound, _ = setup(app, services, tmp_path)
    services.analysis_service = LiveAnalysisApplicationService(
        store=services.store,
        operational_data=ExplicitLiveOperationalPort(),
        work_iq=BoundWorkIQ(),
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="seed-locator",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: NOW,
    )
    services.playback_service = PlaybackService(
        services.uow_factory, clock=ImmediateClock()
    )
    first_payload = issued_payload(client, bound)
    first = client.post("/api/inbox/cases", json=first_payload)
    assert first.status_code == 200, first.text
    first_id = first.json()["case_id"]
    analyzed = client.post(f"/api/cases/{first_id}/analysis")
    assert analyzed.status_code == 201, analyzed.text
    analysis_id = analyzed.json()["analysis_id"]
    review_id, decision_id = seed_complete_earlier_run(
        services.store,
        first_id,
        analysis_id,
        actor,
        services.playback_service,
    )
    earlier_before = client.get(f"/api/cases/{first_id}").json()
    assert earlier_before["current_analysis_id"] == analysis_id
    assert earlier_before["current_decision_id"] == decision_id
    saved_before = saved_earlier_run_values(
        services.store, analysis_id, review_id, decision_id
    )
    assert saved_before["finance_review"][0].reviewed_by is not None
    assert saved_before["finance_review"][0].reviewed_by.persona_id == (
        "RL-PERSONA-TAYLOR"
    )
    assert saved_before["decision"].actor.persona_id == "RL-PERSONA-ALEX"
    assert saved_before["actions"]
    assert saved_before["drafts"]
    assert any(attempts for _, attempts in saved_before["attempts"])
    assert any(events for _, events in saved_before["status_events"])
    assert saved_before["playback"]
    assert saved_before["outcomes"]
    isolated_tables = (
        "analysis_versions",
        "finance_review_revisions",
        "approval_satisfactions",
        "case_proposal_selections",
        "decisions",
        "outbox_events",
        "execution_actions",
        "action_projection",
        "draft_artifacts",
        "execution_events",
        "execution_attempts",
        "playbacks",
        "outcome_observations",
    )
    earlier_counts = presenter_aggregate_counts(services.store, first_id)
    assert all(
        earlier_counts[name] > 0
        for name in (
            "analysis_versions",
            "finance_review_revisions",
            "case_proposal_selections",
            "decisions",
            "execution_actions",
            "action_projection",
            "draft_artifacts",
            "execution_events",
            "execution_attempts",
            "playbacks",
            "outcome_observations",
        )
    )

    second_payload = issued_payload(client, bound)
    second = client.post("/api/inbox/cases", json=second_payload)

    assert second.status_code == 200, second.text
    second_body = second.json()
    second_id = second_body["case_id"]
    assert second_id != first_id
    assert second_payload["presenter_run_id"] != first_payload["presenter_run_id"]
    assert second_body["presenter_run_id"] == second_payload["presenter_run_id"]
    assert second_body["status"] == "open"
    assert second_body["current_analysis_id"] is None
    assert second_body["current_decision_id"] is None
    assert client.get(f"/api/cases/{second_id}/analysis").status_code == 409
    second_counts = presenter_aggregate_counts(services.store, second_id)
    assert all(second_counts[name] == 0 for name in isolated_tables)
    assert client.get(f"/api/cases/{first_id}").json() == earlier_before
    assert (
        saved_earlier_run_values(services.store, analysis_id, review_id, decision_id)
        == saved_before
    )
    assert presenter_aggregate_counts(services.store, first_id) == earlier_counts


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
    assert result.json()["detail"]["code"] == "INBOUND_EMAIL_CHANGED"
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
    _, bound, _ = setup(app, services, tmp_path)
    created = []
    for index in range(5):
        payload = presenter_payload(bound, f"RL-RUN-{index:032x}")
        response = client.post(
            "/api/inbox/cases",
            json=payload,
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
    second_payload = presenter_payload(bound, "RL-RUN-" + "b" * 32)
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
