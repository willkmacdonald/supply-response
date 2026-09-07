from copy import deepcopy
from datetime import UTC, datetime

import pytest

from data.domain.common import RuntimeMode
from data.domain.evidence import AuthorityScope, EvidenceSourceSystem
from integrations.workiq.models import SourceBinding
from tests.auth.test_token_authorization import ALEX_OID, TENANT_ID

BINDING = SourceBinding(
    TENANT_ID,
    ALEX_OID,
    "dispatch@alpha.example",
    "jordan-fixture",
    "team-fixture",
    "19:channel-fixture@thread.tacv2",
    "mail-fixture",
    "1770000000000",
)
NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
MAIL_LINK = "https://outlook.office.com/mail/deeplink/read/mail-fixture"
TEAMS_LINK = (
    "https://teams.microsoft.com/l/message/19%3Achannel-fixture%40thread.tacv2/1770000000000"
    f"?groupId=team-fixture&tenantId={TENANT_ID}"
)
MAIL = {
    "id": "mail-fixture",
    "sender": {"emailAddress": {"address": "dispatch@alpha.example"}},
    "from": {"emailAddress": {"address": "dispatch@alpha.example"}},
    "receivedDateTime": "2026-09-06T16:45:00+02:00",
    "webLink": MAIL_LINK,
    "body": {
        "contentType": "html",
        "content": "<p>Alpha can dispatch 73 units.</p><p>Arrival remains unconfirmed &amp; provisional.</p>",
    },
}
QUALITY = {
    "id": "1770000000000",
    "from": {"user": {"id": "jordan-fixture"}},
    "channelIdentity": {"teamId": "team-fixture", "channelId": BINDING.channel_id},
    "createdDateTime": "2026-09-06T13:12:00Z",
    "webUrl": TEAMS_LINK,
    "deletedDateTime": None,
    "body": {
        "contentType": "text",
        "content": "Beta evaluation covers lot Z-47 only. Further review remains open.",
    },
}


def build(entity, kind="supplier", location=None, binding=BINDING):
    from integrations.workiq.locations import parse_location
    from integrations.workiq.message_evidence import evidence_from_message

    return evidence_from_message(
        entity,
        location=parse_location(
            location or (MAIL_LINK if kind == "supplier" else TEAMS_LINK)
        ),
        binding=binding,
        case_id="case-fixture",
        analysis_id="analysis-fixture",
        retrieved_at=NOW,
    )


@pytest.mark.parametrize(
    "kind,entity,text,scope",
    [
        (
            "supplier",
            MAIL,
            "Alpha can dispatch 73 units. Arrival remains unconfirmed & provisional.",
            AuthorityScope.SUPPLIER_STATEMENT,
        ),
        (
            "quality",
            QUALITY,
            QUALITY["body"]["content"],
            AuthorityScope.COLLABORATION_STATEMENT,
        ),
    ],
)
def test_only_normalized_fetched_statement_is_evidence(kind, entity, text, scope):
    evidence = build(entity, kind)
    assert evidence.claim == evidence.excerpt == text
    assert evidence.source_id == entity["id"]
    assert evidence.authority_scope == (scope,)
    assert evidence.source_system is EvidenceSourceSystem.WORK_IQ
    assert evidence.runtime_mode is RuntimeMode.LIVE
    assert evidence.synthetic is False
    assert evidence.effective_at is None and evidence.expires_at is None
    assert evidence.source_timestamp == datetime.fromisoformat(
        entity.get("receivedDateTime", entity.get("createdDateTime"))
    )
    assert evidence.evidence_id.startswith("workiq-")
    assert evidence.citation_url == entity.get("webLink", entity.get("webUrl"))


@pytest.mark.parametrize(
    "kind,mutation",
    [
        ("supplier", {"id": "wrong"}),
        ("quality", {"id": "wrong"}),
        ("supplier", {"sender": {"emailAddress": {"address": "attacker@example.com"}}}),
        ("supplier", {"from": {"emailAddress": {"address": "attacker@example.com"}}}),
        ("supplier", {"sender": None}),
        ("quality", {"from": {"user": {"displayName": "Jordan", "id": "attacker"}}}),
        (
            "quality",
            {"channelIdentity": {"teamId": "other", "channelId": BINDING.channel_id}},
        ),
        ("quality", {"deletedDateTime": "2026-09-06T14:00:00Z"}),
        ("supplier", {"@removed": {"reason": "deleted"}}),
        ("supplier", {"receivedDateTime": "2026-09-06T16:45:00"}),
        ("quality", {"createdDateTime": None}),
        (
            "supplier",
            {"webLink": "https://outlook.office.com/mail/deeplink/read/wrong"},
        ),
        ("supplier", {"sourceUrl": "https://evil.example/message"}),
        ("quality", {"webUrl": TEAMS_LINK.replace(TENANT_ID, "other-tenant")}),
        ("quality", {"body": {"contentType": "markdown", "content": "some content"}}),
        ("supplier", {"body": {"contentType": "text", "content": " "}}),
        ("supplier", {"body": {"contentType": "text", "content": "X" * 16001}}),
        ("quality", {"body": None}),
    ],
)
def test_invalid_fetched_entities_fail_closed(kind, mutation):
    from integrations.workiq.message_evidence import MessageValidationError

    with pytest.raises(MessageValidationError):
        build({**deepcopy(MAIL if kind == "supplier" else QUALITY), **mutation}, kind)


@pytest.mark.parametrize(
    "location", ["/users/other/messages/mail-fixture", "/me/messages/other"]
)
def test_mailbox_and_discovered_identity_must_match(location):
    from integrations.workiq.message_evidence import MessageValidationError

    with pytest.raises(MessageValidationError):
        build(MAIL, location=location)


def test_html_is_inert_and_traceable_without_hidden_content_or_resources():
    entity = deepcopy(MAIL)
    entity["body"]["content"] = (
        "<style>hidden style</style><script>hidden script</script>"
        "<p>Lot&nbsp;A &lt; 90 <b>units</b>.</p><p>Review<br>pending."
        '<img src="https://evil.example/track" onerror="execute()"></p>'
    )
    assert build(entity).claim == "Lot A < 90 units. Review pending."


def test_normalized_limit_accepts_exact_boundary_without_truncation():
    entity = deepcopy(MAIL)
    entity["body"] = {"contentType": "text", "content": "a" * 16000}
    assert build(entity).excerpt == "a" * 16000
