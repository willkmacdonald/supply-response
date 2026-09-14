from copy import deepcopy
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest

from data.domain.inbound import InboundEmailError
from integrations.workiq import inbox
from tests.domain.test_inbound_email import WILL_BODY
from tests.integration.test_workiq_inbox import CHECKED_AT, Session, message, row
from tests.integration.test_workiq_message_evidence import BINDING

BINDING = replace(BINDING, supplier_sender="will@willmacdonald.com")
IDENTITY = "<will's-message@example.com>"


def email(message_id="new-mail"):
    entity = message(message_id)
    entity["internetMessageId"] = IDENTITY
    entity["body"] = {"contentType": "text", "content": WILL_BODY}
    return entity


def review_session(entity, **kwargs):
    metadata = {**row(entity), "internetMessageId": entity["internetMessageId"]}
    return Session([metadata], {entity["id"]: entity}, **kwargs)


async def reviewed(entity=None):
    entity = entity or email()
    result = await inbox.discover_inbox(
        review_session(entity), binding=BINDING, checked_at=CHECKED_AT
    )
    assert getattr(result.messages[0], "review_fingerprint", None)
    return result.messages[0]


@pytest.mark.anyio
async def test_discovery_exposes_actual_facts_and_identity():
    item = await reviewed()
    assert item.internet_message_id == IDENTITY
    assert item.facts.original_quantity == 8000
    assert item.creation_blocker is None


@pytest.mark.anyio
async def test_discovery_marks_missing_identity_and_unsupported_facts():
    entity = email()
    del entity["internetMessageId"]
    result = await inbox.discover_inbox(
        Session([row(entity)], {entity["id"]: entity}),
        binding=BINDING,
        checked_at=CHECKED_AT,
    )
    assert (
        getattr(result.messages[0], "creation_blocker", None)
        == "INBOUND_EMAIL_UNAVAILABLE"
    )
    entity = email()
    entity["body"]["content"] = "Disruption for RL-MAT-10247."
    result = await inbox.discover_inbox(
        review_session(entity), binding=BINDING, checked_at=CHECKED_AT
    )
    assert result.messages[0].creation_blocker == "INBOUND_EMAIL_UNSUPPORTED"


@pytest.mark.anyio
async def test_review_escapes_identity_and_uses_current_locator_after_move():
    before = await reviewed()
    moved = email("moved-mail")
    session = review_session(moved)
    source, evidence = await inbox.review_email(
        session,
        binding=BINDING,
        internet_message_id=IDENTITY,
        review_fingerprint=before.review_fingerprint,
        checked_at=CHECKED_AT,
        case_id="case",
        analysis_id="analysis",
    )
    assert parse_qs(urlsplit(session.paths[0]).query)["$filter"] == [
        "internetMessageId eq '<will''s-message@example.com>'"
    ]
    assert source.message_id == "moved-mail"
    assert source.review_fingerprint == before.review_fingerprint
    assert evidence.source_id == "moved-mail" and evidence.case_id == "case"
    assert source.mailbox_object_id == BINDING.alex_object_id


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change", ["body", "sender", "recipient", "identity", "missing", "multiple", "next"]
)
async def test_review_rejects_changed_untrusted_or_ambiguous_results(change):
    before = await reviewed()
    entity = email()
    session = review_session(entity)
    if change == "body":
        session.entities[entity["id"]]["body"]["content"] = WILL_BODY.replace(
            "7.50", "8.00"
        )
    elif change == "sender":
        session.entities[entity["id"]]["sender"]["emailAddress"]["address"] = (
            "evil@example.com"
        )
    elif change == "recipient":
        session.entities[entity["id"]]["toRecipients"] = []
    elif change == "identity":
        session.entities[entity["id"]]["internetMessageId"] = "<other@example.com>"
    elif change == "missing":
        session.rows = []
    elif change == "multiple":
        session.rows.append(deepcopy(session.rows[0]))
    elif change == "next":
        session.next_link = True
    with pytest.raises(InboundEmailError) as caught:
        await inbox.review_email(
            session,
            binding=BINDING,
            internet_message_id=IDENTITY,
            review_fingerprint=before.review_fingerprint,
            checked_at=CHECKED_AT,
        )
    assert caught.value.code == (
        "INBOUND_EMAIL_CHANGED"
        if change == "body"
        else "INBOUND_EMAIL_UNAVAILABLE"
        if change in {"missing", "next"}
        else "INBOUND_EMAIL_CONFLICT"
    )


@pytest.mark.anyio
async def test_port_review_and_bound_retrieval_reuse_delegation_and_current_locator():
    from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort
    from tests.integration.test_workiq_contract import _authenticated_alex
    from tests.integration.test_workiq_inbox import FakeClient, FakeObo

    _, actor = _authenticated_alex()
    item = await reviewed()
    session = review_session(email())
    session.request_ids = ("review-rpc",)
    port = WorkIQMcpEvidencePort(
        client=FakeClient(session), obo=FakeObo(), binding=BINDING
    )
    assert hasattr(port, "review_inbound_email")
    source = await port.review_inbound_email(
        actor=actor,
        internet_message_id=IDENTITY,
        review_fingerprint=item.review_fingerprint,
        checked_at=CHECKED_AT,
    )
    moved = review_session(email("moved"))
    moved.request_ids = ("moved-rpc",)
    port = WorkIQMcpEvidencePort(
        client=FakeClient(moved), obo=FakeObo(), binding=BINDING
    )
    result = await port.retrieve_bound_supplier_signal(
        actor=actor,
        source=source,
        case_id="bound",
        analysis_id="analysis",
        retrieved_at=CHECKED_AT,
    )
    assert result.evidence[0].source_id == "moved"
    assert result.lineage.source_ids == ("moved",)
    assert result.lineage.request_ids == ("moved-rpc",)


@pytest.mark.anyio
async def test_port_rejects_wrong_mailbox_binding_before_network_and_sanitizes_errors():
    from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort
    from tests.integration.test_workiq_contract import _authenticated_alex
    from tests.integration.test_workiq_inbox import FakeClient, FakeObo
    from tests.persistence.test_inbound_binding import source

    _, actor = _authenticated_alex()
    obo = FakeObo()
    port = WorkIQMcpEvidencePort(
        client=FakeClient(Session([], fail=True)), obo=obo, binding=BINDING
    )
    assert hasattr(port, "retrieve_bound_supplier_signal")
    with pytest.raises(InboundEmailError, match="INBOUND_EMAIL_CONFLICT"):
        await port.retrieve_bound_supplier_signal(
            actor=actor,
            source=source(),
            case_id="bound",
            analysis_id="analysis",
            retrieved_at=CHECKED_AT,
        )
    assert obo.actors == []
    with pytest.raises(InboundEmailError, match="INBOUND_EMAIL_UNAVAILABLE") as caught:
        await port.review_inbound_email(
            actor=actor,
            internet_message_id=IDENTITY,
            review_fingerprint="a" * 64,
            checked_at=CHECKED_AT,
        )
    assert "private" not in str(caught.value)
