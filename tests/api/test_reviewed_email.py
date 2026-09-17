import asyncio

import pytest

from integrations.graph_mail.client import (
    GraphMailError,
    GraphMailSubmissionUncertain,
)
from services.execution.mail_service import EmailRevisionConflict


class FakeGraphMail:
    def __init__(self, *, send_error=None):
        self.send_error = send_error
        self.send_calls = []

    async def send_message(self, revision, actor):
        self.send_calls.append((revision, actor))
        if self.send_error is not None:
            raise self.send_error


class BlockingGraphMail(FakeGraphMail):
    def __init__(self) -> None:
        super().__init__()
        self.send_started = asyncio.Event()
        self.release_send = asyncio.Event()

    async def send_message(self, revision, actor):
        self.send_calls.append((revision, actor))
        self.send_started.set()
        await self.release_send.wait()


def _enable_mocked_send(services, graph) -> None:
    services.mail_service._graph_mail = graph
    services.mail_service._mail_send_enabled = True


def _approved_decision(client, services):
    created = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": "automated_test"},
    )
    analysis = client.post(f"/api/cases/{created.json()['case_id']}/analysis")
    decision = client.post(
        f"/api/cases/{created.json()['case_id']}/decisions",
        headers={"Idempotency-Key": "RL-REVIEWED-EMAIL-API"},
        json={
            "analysis_id": analysis.json()["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )
    services.run_worker_until_idle()
    return decision.json()["decision_id"]


def test_reviewed_email_routes_version_and_review_without_sending(client, services):
    decision_id = _approved_decision(client, services)

    initial = client.get(f"/api/decisions/{decision_id}/supplier-email")

    assert initial.status_code == 200, initial.text
    assert initial.json()["revision"] == 1
    assert initial.json()["from_address"] == "agent@willmacdonald.com"
    assert initial.json()["to_address"] == "will@willmacdonald.com"
    assert initial.json()["send_status"] == "draft"
    edited = client.put(
        f"/api/decisions/{decision_id}/supplier-email",
        json={
            "revision": 1,
            "subject": "Updated supplier recovery request",
            "body": "Updated fictional demo body.",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["revision"] == 2
    assert edited.json()["reviewed_revision"] is None
    reviewed = client.post(
        f"/api/decisions/{decision_id}/supplier-email/review",
        json={"revision": 2},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewed_revision"] == 2
    assert reviewed.json()["reviewed_by"]["persona_id"] == "RL-PERSONA-ALEX"
    assert reviewed.json()["send_status"] == "draft"
    disabled = client.post(
        f"/api/decisions/{decision_id}/supplier-email/send",
        json={"revision": 2},
    )
    assert disabled.status_code == 409
    assert disabled.json()["detail"]["code"] == "SUPPLIER_EMAIL_SEND_DISABLED"


def test_reviewed_email_request_never_accepts_delivery_fields(client, services):
    decision_id = _approved_decision(client, services)
    path = f"/api/decisions/{decision_id}/supplier-email"
    client.get(path)

    for field, value in (
        ("to_address", "attacker@example.com"),
        ("from_address", "attacker@example.com"),
        ("cc", ["attacker@example.com"]),
        ("bcc", ["attacker@example.com"]),
        ("attachments", [{"name": "payload.bin"}]),
    ):
        response = client.put(
            path,
            json={
                "revision": 1,
                "subject": "Safe subject",
                "body": "Safe body",
                field: value,
            },
        )
        assert response.status_code == 422, (field, response.text)
    current = client.get(path).json()
    assert current["revision"] == 1
    assert current["from_address"] == "agent@willmacdonald.com"
    assert current["to_address"] == "will@willmacdonald.com"


def test_reviewed_email_returns_safe_validation_and_conflict_responses(
    client, services
):
    decision_id = _approved_decision(client, services)
    path = f"/api/decisions/{decision_id}/supplier-email"
    client.get(path)

    for subject, body in (
        (" ", "body"),
        ("x" * 256, "body"),
        ("subject", " "),
        ("subject", "x" * 10_001),
    ):
        invalid = client.put(
            path,
            json={"revision": 1, "subject": subject, "body": body},
        )
        assert invalid.status_code == 422
        assert "traceback" not in invalid.text.lower()

    changed = client.put(
        path,
        json={"revision": 1, "subject": "Changed", "body": "Changed body"},
    )
    assert changed.status_code == 200
    stale = client.put(
        path,
        json={"revision": 1, "subject": "Again", "body": "Again body"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["message"] == (
        "The supplier email changed. Refresh it and try again."
    )
    stale_review = client.post(f"{path}/review", json={"revision": 1})
    assert stale_review.status_code == 409
    assert "traceback" not in stale_review.text.lower()


def _reviewed_email(client, services):
    decision_id = _approved_decision(client, services)
    path = f"/api/decisions/{decision_id}/supplier-email"
    initial = client.get(path)
    assert initial.status_code == 200
    reviewed = client.post(f"{path}/review", json={"revision": 1})
    assert reviewed.status_code == 200
    return decision_id, path


def test_send_uses_one_direct_graph_submission(client, services):
    decision_id, path = _reviewed_email(client, services)
    graph = FakeGraphMail()
    _enable_mocked_send(services, graph)

    sent = client.post(f"{path}/send", json={"revision": 1})
    repeated = client.post(f"{path}/send", json={"revision": 1})

    assert sent.status_code == repeated.status_code == 200
    assert sent.json()["send_status"] == "accepted"
    assert repeated.json() == sent.json()
    assert len(graph.send_calls) == 1
    with services.uow_factory() as uow:
        _, delivery = uow.mail.get_current(decision_id)
    assert delivery.provider_message_id is None
    assert delivery.internet_message_id is None
    assert delivery.correlation_id is not None


def test_send_accepts_only_revision_and_persists_accepted_state(client, services):
    decision_id, path = _reviewed_email(client, services)
    graph = FakeGraphMail()
    _enable_mocked_send(services, graph)

    invalid = client.post(
        f"{path}/send",
        json={"revision": 1, "to_address": "attacker@example.com"},
    )
    sent = client.post(f"{path}/send", json={"revision": 1})
    repeated = client.post(f"{path}/send", json={"revision": 1})

    assert invalid.status_code == 422
    assert sent.status_code == repeated.status_code == 200
    assert sent.json()["send_status"] == "accepted"
    assert repeated.json() == sent.json()
    assert len(graph.send_calls) == 1
    with services.uow_factory() as uow:
        _, delivery = uow.mail.get_current(decision_id)
    assert delivery.provider_message_id is None
    assert delivery.internet_message_id is None
    assert delivery.correlation_id is not None


@pytest.mark.anyio
async def test_concurrent_send_claim_causes_at_most_one_provider_submission(
    client, services
):
    decision_id, _ = _reviewed_email(client, services)
    graph = FakeGraphMail()
    _enable_mocked_send(services, graph)
    actor = services.identity

    first, second = await asyncio.gather(
        services.mail_service.send(decision_id, 1, actor),
        services.mail_service.send(decision_id, 1, actor),
    )

    assert {first.send_status, second.send_status}.issubset({"submitting", "accepted"})
    assert len(graph.send_calls) == 1
    assert services.mail_service.get(decision_id).send_status == "accepted"


@pytest.mark.anyio
async def test_edit_racing_send_cannot_erase_submitting_claim(client, services):
    decision_id, _ = _reviewed_email(client, services)
    graph = BlockingGraphMail()
    _enable_mocked_send(services, graph)

    send = asyncio.create_task(
        services.mail_service.send(decision_id, 1, services.identity)
    )
    await graph.send_started.wait()
    with services.uow_factory() as uow:
        before = uow.mail.get_current(decision_id)
    assert before is not None
    assert before[1].send_status == "submitting"

    with pytest.raises(EmailRevisionConflict):
        services.mail_service.save(
            decision_id,
            1,
            "Unsafe racing edit",
            "This must not replace submitted content.",
            services.identity,
        )

    with services.uow_factory() as uow:
        after = uow.mail.get_current(decision_id)
    assert after == before
    graph.release_send.set()
    result = await send
    repeated = await services.mail_service.send(decision_id, 1, services.identity)

    assert result.send_status == repeated.send_status == "accepted"
    assert len(graph.send_calls) == 1


@pytest.mark.parametrize(
    "send_status",
    ["accepted", "uncertain"],
)
def test_edit_after_provider_submission_preserves_tracking_and_cannot_resubmit(
    client,
    services,
    send_status,
):
    decision_id, path = _reviewed_email(client, services)
    graph = FakeGraphMail(
        send_error=(
            GraphMailSubmissionUncertain("graph_send_uncertain")
            if send_status == "uncertain"
            else None
        ),
    )
    _enable_mocked_send(services, graph)
    sent = client.post(f"{path}/send", json={"revision": 1})
    assert sent.json()["send_status"] == send_status
    with services.uow_factory() as uow:
        before = uow.mail.get_current(decision_id)

    edited = client.put(
        path,
        json={
            "revision": 1,
            "subject": "Unsafe post-send edit",
            "body": "This must preserve provider tracking.",
        },
    )
    repeated = client.post(f"{path}/send", json={"revision": 1})
    with services.uow_factory() as uow:
        after = uow.mail.get_current(decision_id)

    assert edited.status_code == 409
    assert repeated.status_code == 200
    assert repeated.json()["send_status"] == send_status
    assert after == before
    assert len(graph.send_calls) == 1


def test_graph_rejection_is_failed(client, services):
    _, path = _reviewed_email(client, services)
    graph = FakeGraphMail(send_error=GraphMailError("graph_send_failed"))
    _enable_mocked_send(services, graph)

    response = client.post(f"{path}/send", json={"revision": 1})

    assert response.status_code == 200
    assert response.json()["send_status"] == "failed"
    assert len(graph.send_calls) == 1


def test_failure_before_provider_submission_remains_editable(client, services):
    decision_id, path = _reviewed_email(client, services)
    graph = FakeGraphMail(send_error=GraphMailError("graph_send_failed"))
    _enable_mocked_send(services, graph)

    failed = client.post(f"{path}/send", json={"revision": 1})
    with services.uow_factory() as uow:
        before_edit = uow.mail.get_current(decision_id)
    edited = client.put(
        path,
        json={
            "revision": 1,
            "subject": "Safe retry content",
            "body": "No provider submission occurred.",
        },
    )

    assert failed.json()["send_status"] == "failed"
    assert before_edit is not None
    assert before_edit[1].provider_message_id is None
    assert len(graph.send_calls) == 1
    assert edited.status_code == 200
    assert edited.json()["revision"] == 2
    assert edited.json()["send_status"] == "draft"


def test_indeterminate_send_cannot_repeat_or_claim_confirmation(client, services):
    _, path = _reviewed_email(client, services)
    graph = FakeGraphMail(
        send_error=GraphMailSubmissionUncertain("graph_send_uncertain"),
    )
    _enable_mocked_send(services, graph)

    uncertain = client.post(f"{path}/send", json={"revision": 1})
    repeated = client.post(f"{path}/send", json={"revision": 1})
    checked = client.post(f"{path}/check-send-status")

    assert uncertain.status_code == repeated.status_code == 200
    assert checked.status_code == 409
    assert uncertain.json()["send_status"] == "uncertain"
    assert repeated.json() == uncertain.json()
    assert len(graph.send_calls) == 1
