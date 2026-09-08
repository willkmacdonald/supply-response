import asyncio
from collections.abc import Mapping
from copy import deepcopy

import pytest

from integrations.workiq.models import SourceBinding
from tests.integration.test_workiq_message_evidence import BINDING

MAIL_QUERY = (
    "/me/messages?$search=%22RL-Supplier%20Alpha%22&$top=5&"
    "$select=id,subject,from,receivedDateTime"
)


class Session:
    def __init__(self, pages: Mapping[str, object]) -> None:
        self.pages = pages
        self.paths: list[str] = []

    async def fetch(self, entity_url: str) -> dict[str, object]:
        self.paths.append(entity_url)
        page = self.pages[entity_url]
        if isinstance(page, BaseException):
            raise page
        return {"results": [{"statusCode": 200, "data": deepcopy(page)}]}

    async def ask(self, question):
        pytest.fail("structured discovery called ask")


def collection(rows, **extra):
    return {"value": rows, **extra}


@pytest.mark.anyio
async def test_supplier_uses_one_fixed_bounded_metadata_query_and_returned_id():
    from integrations.workiq.structured_discovery import discover_structured

    session = Session(
        {
            MAIL_QUERY: collection(
                [
                    {
                        "id": BINDING.supplier_source_id,
                        "subject": "RL-Supplier Alpha message",
                        "from": {"emailAddress": {"address": BINDING.supplier_sender}},
                        "receivedDateTime": "2026-09-06T14:45:00Z",
                    }
                ]
            )
        }
    )
    found = await discover_structured(session, source_kind="supplier", binding=BINDING)
    assert found[0].message_id == BINDING.supplier_source_id
    assert found[0].fetch_path == f"/me/messages/{BINDING.supplier_source_id}"
    assert session.paths == [MAIL_QUERY]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "rows",
    [
        [],
        [
            {
                "id": "one",
                "subject": "RL-Supplier Alpha",
                "from": {"emailAddress": {"address": BINDING.supplier_sender}},
                "receivedDateTime": "2026-09-06T14:45:00Z",
            },
            {
                "id": "two",
                "subject": "RL-Supplier Alpha",
                "from": {"emailAddress": {"address": BINDING.supplier_sender}},
                "receivedDateTime": "2026-09-06T14:46:00Z",
            },
        ],
        [{"id": "one", "subject": "RL-Supplier Alpha", "from": None}],
        [
            {
                "id": "../hostile",
                "subject": "RL-Supplier Alpha",
                "from": {"emailAddress": {"address": BINDING.supplier_sender}},
                "receivedDateTime": "2026-09-06T14:45:00Z",
            }
        ],
    ],
)
async def test_supplier_rejects_empty_duplicate_malformed_and_hostile_candidates(rows):
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    session = Session({MAIL_QUERY: collection(rows)})
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(session, source_kind="supplier", binding=BINDING)
    assert session.paths == [MAIL_QUERY]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "data",
    [
        {"value": "bad"},
        collection([{}] * 6),
        collection([], **{"@odata.nextLink": "private-next"}),
        collection([], nextLink="private-next"),
    ],
)
async def test_supplier_rejects_invalid_oversized_or_paginated_collection(data):
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(
            Session({MAIL_QUERY: data}), source_kind="supplier", binding=BINDING
        )


@pytest.mark.anyio
async def test_source_ids_validate_only_and_never_disambiguate_or_build_paths():
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    rows = [
        {
            "id": value,
            "subject": "RL-Supplier Alpha",
            "from": {"emailAddress": {"address": BINDING.supplier_sender}},
            "receivedDateTime": "2026-09-06T14:45:00Z",
        }
        for value in (BINDING.supplier_source_id, "other")
    ]
    session = Session({MAIL_QUERY: collection(rows)})
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(session, source_kind="supplier", binding=BINDING)
    assert BINDING.supplier_source_id not in session.paths[0]


@pytest.mark.anyio
async def test_mail_rejects_duplicate_identity_before_candidate_filtering():
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    rows = [
        {
            "id": BINDING.supplier_source_id,
            "subject": subject,
            "from": {"emailAddress": {"address": BINDING.supplier_sender}},
            "receivedDateTime": "2026-09-06T14:45:00Z",
        }
        for subject in ("RL-Supplier Alpha message", "Unrelated")
    ]
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(
            Session({MAIL_QUERY: collection(rows)}),
            source_kind="supplier",
            binding=BINDING,
        )


@pytest.mark.anyio
async def test_quality_resolves_exact_scope_then_selects_unique_jordan_beta_post():
    from integrations.workiq.structured_discovery import discover_structured

    teams = "/me/joinedTeams"
    channels = "/teams/team-returned/channels"
    posts = (
        "/teams/team-returned/channels/19%3Areturned%40thread.tacv2/messages?$top=10"
    )
    session = Session(
        {
            teams: collection(
                [{"id": "team-returned", "displayName": "Supply Response Demo"}]
            ),
            channels: collection(
                [{"id": "19:returned@thread.tacv2", "displayName": "General"}]
            ),
            posts: collection(
                [
                    {
                        "id": BINDING.quality_source_id,
                        "from": {
                            "user": {
                                "id": BINDING.quality_author_object_id,
                                "displayName": "Jordan Lee",
                            }
                        },
                        "body": {
                            "contentType": "text",
                            "content": "RL-Supplier Beta qualification is pending.",
                        },
                    }
                ]
            ),
        }
    )
    binding = SourceBinding(
        BINDING.tenant_id,
        BINDING.alex_object_id,
        BINDING.supplier_sender,
        BINDING.quality_author_object_id,
        "team-returned",
        "19:returned@thread.tacv2",
        BINDING.supplier_source_id,
        BINDING.quality_source_id,
    )
    found = await discover_structured(session, source_kind="quality", binding=binding)
    assert found[0].fetch_path == (
        f"/teams/team-returned/channels/19%3Areturned%40thread.tacv2/messages/{BINDING.quality_source_id}"
    )
    assert session.paths == [teams, channels, posts]


@pytest.mark.anyio
@pytest.mark.parametrize("scope", ["team", "channel"])
async def test_quality_validates_scope_before_reading_children(scope):
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    team_id = "wrong" if scope == "team" else BINDING.team_id
    pages = {
        "/me/joinedTeams": collection(
            [{"id": team_id, "displayName": "Supply Response Demo"}]
        ),
    }
    if scope == "channel":
        pages[f"/teams/{BINDING.team_id}/channels"] = collection(
            [{"id": "wrong", "displayName": "General"}]
        )
    session = Session(pages)
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(session, source_kind="quality", binding=BINDING)
    assert len(session.paths) == (1 if scope == "team" else 2)


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["team", "channel"])
async def test_quality_rejects_malformed_nonmatching_scope_identity(kind):
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    pages: dict[str, object] = {
        "/me/joinedTeams": collection(
            [
                {"id": BINDING.team_id, "displayName": "Supply Response Demo"},
                *(
                    [{"id": "../hostile", "displayName": "Other"}]
                    if kind == "team"
                    else []
                ),
            ]
        )
    }
    if kind == "channel":
        pages[f"/teams/{BINDING.team_id}/channels"] = collection(
            [
                {"id": BINDING.channel_id, "displayName": "General"},
                {"id": "../hostile", "displayName": "Other"},
            ]
        )
    session = Session(pages)
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(session, source_kind="quality", binding=BINDING)
    assert len(session.paths) == (1 if kind == "team" else 2)


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["team", "channel"])
async def test_quality_rejects_duplicate_scope_identity_before_name_filtering(kind):
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    pages: dict[str, object] = {
        "/me/joinedTeams": collection(
            [
                {"id": BINDING.team_id, "displayName": "Supply Response Demo"},
                *(
                    [{"id": BINDING.team_id, "displayName": "Other"}]
                    if kind == "team"
                    else []
                ),
            ]
        )
    }
    if kind == "channel":
        pages[f"/teams/{BINDING.team_id}/channels"] = collection(
            [
                {"id": BINDING.channel_id, "displayName": "General"},
                {"id": BINDING.channel_id, "displayName": "Other"},
            ]
        )
    session = Session(pages)
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(session, source_kind="quality", binding=BINDING)
    assert len(session.paths) == (1 if kind == "team" else 2)


@pytest.mark.anyio
async def test_quality_rejects_author_or_beta_topic_mismatch_without_saved_id_fallback():
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    posts = f"/teams/{BINDING.team_id}/channels/19%3Achannel-fixture%40thread.tacv2/messages?$top=10"
    session = Session(
        {
            "/me/joinedTeams": collection(
                [{"id": BINDING.team_id, "displayName": "Supply Response Demo"}]
            ),
            f"/teams/{BINDING.team_id}/channels": collection(
                [{"id": BINDING.channel_id, "displayName": "General"}]
            ),
            posts: collection(
                [
                    {
                        "id": "other",
                        "from": {"user": {"id": "wrong", "displayName": "Jordan Lee"}},
                        "body": {"contentType": "text", "content": "Alpha topic"},
                    }
                ]
            ),
        }
    )
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(session, source_kind="quality", binding=BINDING)
    assert all(BINDING.quality_source_id not in path for path in session.paths)


@pytest.mark.anyio
async def test_quality_ignores_well_formed_deleted_tombstone_before_jordan_post():
    from integrations.workiq.structured_discovery import discover_structured

    posts = f"/teams/{BINDING.team_id}/channels/19%3Achannel-fixture%40thread.tacv2/messages?$top=10"
    session = Session(
        {
            "/me/joinedTeams": collection(
                [{"id": BINDING.team_id, "displayName": "Supply Response Demo"}]
            ),
            f"/teams/{BINDING.team_id}/channels": collection(
                [{"id": BINDING.channel_id, "displayName": "General"}]
            ),
            posts: collection(
                [
                    {
                        "id": "deleted-post",
                        "deletedDateTime": "2026-09-01T10:00:00Z",
                        "from": {"user": {"id": "will"}},
                        "body": {"contentType": "text", "content": ""},
                    },
                    {
                        "id": BINDING.quality_source_id,
                        "deletedDateTime": None,
                        "from": {"user": {"id": BINDING.quality_author_object_id}},
                        "body": {
                            "contentType": "text",
                            "content": "RL-Supplier Beta qualification is pending.",
                        },
                    },
                ]
            ),
        }
    )
    found = await discover_structured(session, source_kind="quality", binding=BINDING)
    assert found[0].message_id == BINDING.quality_source_id


@pytest.mark.anyio
async def test_quality_rejects_duplicate_post_identity_before_candidate_filtering():
    from integrations.workiq.structured_discovery import (
        StructuredDiscoveryError,
        discover_structured,
    )

    posts = f"/teams/{BINDING.team_id}/channels/19%3Achannel-fixture%40thread.tacv2/messages?$top=10"
    pages: dict[str, object] = {
        "/me/joinedTeams": collection(
            [{"id": BINDING.team_id, "displayName": "Supply Response Demo"}]
        ),
        f"/teams/{BINDING.team_id}/channels": collection(
            [{"id": BINDING.channel_id, "displayName": "General"}]
        ),
        posts: collection(
            [
                {
                    "id": BINDING.quality_source_id,
                    "from": {"user": {"id": BINDING.quality_author_object_id}},
                    "body": {
                        "contentType": "text",
                        "content": "RL-Supplier Beta qualification is pending.",
                    },
                },
                {
                    "id": BINDING.quality_source_id,
                    "from": {"user": {"id": "other"}},
                    "body": {"contentType": "text", "content": "Other"},
                },
            ]
        ),
    }
    with pytest.raises(StructuredDiscoveryError):
        await discover_structured(
            Session(pages), source_kind="quality", binding=BINDING
        )


@pytest.mark.anyio
async def test_cancellation_is_not_converted_to_discovery_failure():
    from integrations.workiq.structured_discovery import discover_structured

    class Blocking(Session):
        async def fetch(self, entity_url: str) -> dict[str, object]:
            self.paths.append(entity_url)
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    task = asyncio.create_task(
        discover_structured(Blocking({}), source_kind="supplier", binding=BINDING)
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
