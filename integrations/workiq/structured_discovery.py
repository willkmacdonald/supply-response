"""Bounded Work IQ entity discovery using independently returned identities."""

from collections.abc import Mapping
from datetime import datetime
from typing import Final, Protocol, cast
from urllib.parse import quote

from .locations import MessageLocation, parse_location
from .models import SourceBinding, SourceKind

MAIL_QUERY: Final = (
    "/me/messages?$search=%22RL-Supplier%20Alpha%22&$top=5&"
    "$select=id,subject,from,receivedDateTime"
)
TEAMS_QUERY: Final = "/me/joinedTeams"
TEAM_NAME: Final = "Supply Response Demo"
CHANNEL_NAME: Final = "General"


class StructuredDiscoveryError(ValueError):
    """A structured collection was unsafe, out of scope, or ambiguous."""

    def __init__(self, reason: str) -> None:
        allowed = {
            "mail_collection",
            "mail_candidate",
            "team_collection",
            "team_scope",
            "channel_collection",
            "channel_scope",
            "post_collection",
            "post_candidate",
        }
        self.reason = reason if reason in allowed else "collection_invalid"
        super().__init__(self.reason)


class FetchSession(Protocol):
    async def fetch(self, entity_url: str) -> dict[str, object]: ...


def _collection(
    payload: object, *, maximum: int, reason: str
) -> list[Mapping[str, object]]:
    if not isinstance(payload, dict):
        raise StructuredDiscoveryError(reason)
    results = payload.get("results")
    if (
        not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], dict)
        or results[0].get("statusCode") != 200
        or not isinstance(results[0].get("data"), dict)
    ):
        raise StructuredDiscoveryError(reason)
    data = results[0]["data"]
    assert isinstance(data, dict)
    if "@odata.nextLink" in data or "nextLink" in data:
        raise StructuredDiscoveryError(reason)
    rows = data.get("value")
    if not isinstance(rows, list) or len(rows) > maximum:
        raise StructuredDiscoveryError(reason)
    if any(not isinstance(row, dict) for row in rows):
        raise StructuredDiscoveryError(reason)
    return cast(list[Mapping[str, object]], rows)


def _identity(value: object, path: str, source_kind: SourceKind) -> MessageLocation:
    if not isinstance(value, str):
        raise StructuredDiscoveryError("identity")
    location = parse_location(path.format(identity=quote(value, safe="")))
    if location is None or location.source_kind != source_kind:
        raise StructuredDiscoveryError("identity")
    return location


def _mail_candidate(row: Mapping[str, object], binding: SourceBinding) -> bool:
    identity = row.get("id")
    subject = row.get("subject")
    sender = row.get("from")
    received = row.get("receivedDateTime")
    _identity(identity, "/me/messages/{identity}", "supplier")
    if not isinstance(subject, str) or not isinstance(sender, dict):
        raise StructuredDiscoveryError("mail row")
    address = sender.get("emailAddress")
    if not isinstance(address, dict) or not isinstance(address.get("address"), str):
        raise StructuredDiscoveryError("mail row")
    if not isinstance(received, str):
        raise StructuredDiscoveryError("mail row")
    try:
        datetime.fromisoformat(received)
    except ValueError:
        raise StructuredDiscoveryError("mail_collection") from None
    return (
        "RL-Supplier Alpha" in subject
        and address["address"].casefold() == binding.supplier_sender.casefold()
    )


def _named_id(
    row: Mapping[str, object], *, expected_name: str, reason: str
) -> tuple[str, bool]:
    identity, name = row.get("id"), row.get("displayName")
    if not isinstance(identity, str) or not isinstance(name, str):
        raise StructuredDiscoveryError(reason)
    return identity, name == expected_name


async def discover_structured(
    session: FetchSession, *, source_kind: SourceKind, binding: SourceBinding
) -> tuple[MessageLocation, ...]:
    """Discover exactly one independently selected and configured message."""
    if source_kind == "supplier":
        rows = _collection(
            await session.fetch(MAIL_QUERY), maximum=5, reason="mail_collection"
        )
        mail_matches = [row for row in rows if _mail_candidate(row, binding)]
        if len(mail_matches) != 1:
            raise StructuredDiscoveryError("mail_candidate")
        location = _identity(
            mail_matches[0]["id"], "/me/messages/{identity}", "supplier"
        )
        return (location,)

    teams = _collection(
        await session.fetch(TEAMS_QUERY), maximum=25, reason="team_collection"
    )
    named_teams = [
        identity
        for row in teams
        for identity, matches in [
            _named_id(row, expected_name=TEAM_NAME, reason="team_collection")
        ]
        if matches
    ]
    if len(named_teams) != 1:
        raise StructuredDiscoveryError("team_scope")
    team_id = named_teams[0]
    _identity(team_id, "/teams/{identity}/channels/x/messages/x", "quality")
    if team_id != binding.team_id:
        raise StructuredDiscoveryError("team_scope")

    channel_path = f"/teams/{quote(team_id, safe='')}/channels"
    channels = _collection(
        await session.fetch(channel_path), maximum=25, reason="channel_collection"
    )
    named_channels = [
        identity
        for row in channels
        for identity, matches in [
            _named_id(row, expected_name=CHANNEL_NAME, reason="channel_collection")
        ]
        if matches
    ]
    if len(named_channels) != 1:
        raise StructuredDiscoveryError("channel_scope")
    channel_id = named_channels[0]
    _identity(
        channel_id,
        f"/teams/{quote(team_id, safe='')}/channels/{{identity}}/messages/x",
        "quality",
    )
    if channel_id != binding.channel_id:
        raise StructuredDiscoveryError("channel_scope")

    base = f"/teams/{quote(team_id, safe='')}/channels/{quote(channel_id, safe='')}"
    posts = _collection(
        await session.fetch(f"{base}/messages?$top=10"),
        maximum=10,
        reason="post_collection",
    )
    post_matches: list[MessageLocation] = []
    for post in posts:
        location = _identity(post.get("id"), f"{base}/messages/{{identity}}", "quality")
        author, body = post.get("from"), post.get("body")
        deleted = post.get("deletedDateTime")
        if deleted is not None:
            if not isinstance(deleted, str) or author is not None or body is not None:
                raise StructuredDiscoveryError("post_collection")
            try:
                datetime.fromisoformat(deleted)
            except ValueError:
                raise StructuredDiscoveryError("post_collection") from None
            continue
        if not isinstance(author, dict) or not isinstance(body, dict):
            raise StructuredDiscoveryError("post_collection")
        user = author.get("user")
        content, content_type = body.get("content"), body.get("contentType")
        if (
            not isinstance(user, dict)
            or not isinstance(user.get("id"), str)
            or not isinstance(content, str)
            or content_type not in ("text", "html")
        ):
            raise StructuredDiscoveryError("post_collection")
        if (
            user["id"] == binding.quality_author_object_id
            and "RL-Supplier Beta" in content
        ):
            post_matches.append(location)
    if len(post_matches) != 1:
        raise StructuredDiscoveryError("post_candidate")
    return (post_matches[0],)
