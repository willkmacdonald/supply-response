from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.integration.test_workiq_message_evidence import BINDING, MAIL

CHECKED_AT = datetime(2026, 9, 14, 15, tzinfo=UTC)
SUBJECT = "[Supply Response Demo] RL-001 | Supplier Alpha | Demo run 0914-A"


def message(message_id="new-mail"):
    entity = deepcopy(MAIL)
    entity.update(
        {
            "id": message_id,
            "subject": SUBJECT,
            "sender": {"emailAddress": {"address": "will@willmacdonald.com"}},
            "from": {"emailAddress": {"address": "will@willmacdonald.com"}},
            "toRecipients": [{"emailAddress": {"address": "agent@willmacdonald.com"}}],
            "webLink": f"https://outlook.office.com/mail/deeplink/read/{message_id}",
            "body": {
                "contentType": "html",
                "content": "<p>Disruption for RL-MAT-10247.</p>",
            },
        }
    )
    return entity


def row(entity):
    return {
        key: deepcopy(entity[key])
        for key in (
            "id",
            "subject",
            "sender",
            "from",
            "toRecipients",
            "receivedDateTime",
        )
    }


class Session:
    def __init__(self, rows, entities=None, *, next_link=False, fail=None):
        self.rows = rows
        self.entities = entities or {}
        self.next_link = next_link
        self.fail = fail
        self.paths = []

    async def fetch(self, path):
        self.paths.append(path)
        if self.fail == path or self.fail is True:
            raise RuntimeError("private transport details")
        if len(self.paths) == 1:
            data = {"value": deepcopy(self.rows)}
            if self.next_link:
                data["@odata.nextLink"] = "https://evil.example/continue"
            return {"results": [{"statusCode": 200, "data": data}]}
        message_id = path.rsplit("/", 1)[-1]
        return {
            "results": [
                {"statusCode": 200, "data": deepcopy(self.entities[message_id])}
            ]
        }


@pytest.fixture
def binding():
    return replace(BINDING, supplier_sender="will@willmacdonald.com")


@pytest.mark.anyio
async def test_empty_bounded_collection_is_complete(binding):
    from integrations.workiq.inbox import discover_inbox

    session = Session([])
    result = await discover_inbox(session, binding=binding, checked_at=CHECKED_AT)
    assert result.checked_at == CHECKED_AT
    assert result.messages == []
    assert result.incomplete is False
    assert "$top=25" in session.paths[0] and "$search=" in session.paths[0]
    assert parse_qs(urlsplit(session.paths[0]).query)["$search"] == ['"subject:RL-001"']


@pytest.mark.anyio
async def test_preview_is_bounded_after_body_validation(binding):
    from integrations.workiq.inbox import discover_inbox

    entity = message()
    entity["body"] = {"contentType": "text", "content": "RL-MAT-10247 " + "x" * 5000}
    result = await discover_inbox(
        Session([row(entity)], {entity["id"]: entity}),
        binding=binding,
        checked_at=CHECKED_AT,
    )
    assert len(result.messages[0].excerpt) <= 4001
    assert result.messages[0].excerpt.endswith("…")


@pytest.mark.anyio
async def test_returns_new_non_seed_message_and_does_not_mutate_binding(binding):
    from integrations.workiq.inbox import discover_inbox

    entity = message()
    result = await discover_inbox(
        Session([row(entity)], {entity["id"]: entity}),
        binding=binding,
        checked_at=CHECKED_AT,
    )
    assert binding.supplier_source_id == BINDING.supplier_source_id
    assert [item.message_id for item in result.messages] == ["new-mail"]
    assert result.messages[0].subject == SUBJECT
    assert result.messages[0].sender == "will@willmacdonald.com"
    assert result.messages[0].excerpt == "Disruption for RL-MAT-10247."
    assert result.incomplete is False


@pytest.mark.anyio
async def test_multiple_candidates_are_returned_in_collection_order(binding):
    from integrations.workiq.inbox import discover_inbox

    entities = {name: message(name) for name in ("one", "two")}
    result = await discover_inbox(
        Session([row(value) for value in entities.values()], entities),
        binding=binding,
        checked_at=CHECKED_AT,
    )
    assert [item.message_id for item in result.messages] == ["one", "two"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation",
    [
        {"sender": {"emailAddress": {"address": "attacker@example.com"}}},
        {"from": {"emailAddress": {"address": "attacker@example.com"}}},
        {"toRecipients": [{"emailAddress": {"address": "other@example.com"}}]},
        {"subject": "[Supply Response Demo] RL-001 other supplier"},
        {"body": {"contentType": "text", "content": "a different material"}},
        {"webLink": "https://evil.example/message"},
    ],
)
async def test_retrieved_candidate_must_meet_every_marker(binding, mutation):
    from integrations.workiq.inbox import discover_inbox

    good = message()
    bad = {**deepcopy(good), **mutation}
    result = await discover_inbox(
        Session([row(good)], {good["id"]: bad}),
        binding=binding,
        checked_at=CHECKED_AT,
    )
    assert result.messages == []
    assert result.incomplete is True


@pytest.mark.anyio
async def test_html_is_inert_in_preview(binding):
    from integrations.workiq.inbox import discover_inbox

    entity = message()
    entity["body"]["content"] = (
        "<script>steal()</script><p>RL-MAT-10247 delayed &amp; under review.</p>"
    )
    result = await discover_inbox(
        Session([row(entity)], {entity["id"]: entity}),
        binding=binding,
        checked_at=CHECKED_AT,
    )
    assert result.messages[0].excerpt == "RL-MAT-10247 delayed & under review."
    assert "steal" not in result.messages[0].excerpt


@pytest.mark.anyio
async def test_next_link_and_more_than_five_body_candidates_are_incomplete(binding):
    from integrations.workiq.inbox import discover_inbox

    entities = {str(index): message(str(index)) for index in range(6)}
    session = Session(
        [row(value) for value in entities.values()], entities, next_link=True
    )
    result = await discover_inbox(session, binding=binding, checked_at=CHECKED_AT)
    assert len(result.messages) == 5
    assert result.incomplete is True
    assert len(session.paths) == 6


@pytest.mark.anyio
async def test_failed_candidate_read_is_incomplete_not_fabricated_empty(binding):
    from integrations.workiq.inbox import discover_inbox

    entity = message()
    session = Session(
        [row(entity)], {entity["id"]: entity}, fail="/me/messages/new-mail"
    )
    result = await discover_inbox(session, binding=binding, checked_at=CHECKED_AT)
    assert result.messages == [] and result.incomplete is True


class FakeObo:
    def __init__(self):
        self.actors = []

    async def exchange(self, actor):
        self.actors.append(actor)

        class Token:
            def reveal(self):
                return "delegated-token"

        return Token()


class FakeClient:
    def __init__(self, session):
        self.value = session
        self.tokens = []

    @asynccontextmanager
    async def session(self, *, access_token):
        self.tokens.append(access_token)
        yield self.value


@pytest.mark.anyio
async def test_port_checks_actor_and_uses_one_obo_session(binding):
    from integrations.workiq.mcp_evidence import WorkIQMcpEvidencePort
    from tests.integration.test_workiq_contract import _authenticated_alex

    _service, actor = _authenticated_alex()
    session, obo = Session([]), FakeObo()
    client = FakeClient(session)
    port = WorkIQMcpEvidencePort(client=client, obo=obo, binding=binding)
    result = await port.check_inbox(actor=actor, checked_at=CHECKED_AT)
    assert result.messages == [] and result.incomplete is False
    assert obo.actors == [actor] and client.tokens == ["delegated-token"]


@pytest.mark.anyio
async def test_port_sanitizes_transport_failure(binding):
    from integrations.workiq.mcp_evidence import (
        WorkIQMcpEvidencePort,
        WorkIQSourceError,
    )
    from tests.integration.test_workiq_contract import _authenticated_alex

    _service, actor = _authenticated_alex()
    port = WorkIQMcpEvidencePort(
        client=FakeClient(Session([], fail=True)), obo=FakeObo(), binding=binding
    )
    with pytest.raises(WorkIQSourceError) as caught:
        await port.check_inbox(actor=actor, checked_at=CHECKED_AT)
    assert caught.value.stage == "discovery"
    assert caught.value.__context__ is None
