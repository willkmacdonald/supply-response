"""Validate fetched messages and retain their inert source statement, never ask prose."""

from collections.abc import Mapping
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from uuid import uuid4

from data.domain.common import RuntimeMode
from data.domain.evidence import (
    AuthorityScope,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    RetrievalHealth,
    UncertaintyState,
)

from .errors import WorkIQError
from .locations import MessageLocation, parse_location
from .models import SourceBinding


class MessageValidationError(WorkIQError):
    def __init__(self) -> None:
        super().__init__("Work IQ message rejected")


class _InertText(HTMLParser):
    _hidden = frozenset(
        {"script", "style", "iframe", "object", "svg", "math", "template"}
    )
    _blocks = frozenset(
        {
            "p",
            "div",
            "br",
            "li",
            "ul",
            "ol",
            "tr",
            "td",
            "th",
            "table",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "pre",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._hidden:
            self.hidden.append(tag)
        elif not self.hidden and tag in self._blocks:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.hidden:
            if self.hidden[-1] == tag:
                self.hidden.pop()
        elif tag in self._blocks:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _text(body: Any) -> str:
    if not isinstance(body, Mapping) or not isinstance(body.get("content"), str):
        raise MessageValidationError()
    content = body["content"]
    if len(content) > 1024 * 1024:
        raise MessageValidationError()
    content_type = body.get("contentType")
    if isinstance(content_type, str) and content_type.lower() == "html":
        parser = _InertText()
        parser.feed(content)
        parser.close()
        content = "".join(parser.parts)
    elif not isinstance(content_type, str) or content_type.lower() != "text":
        raise MessageValidationError()
    normalized = " ".join(content.split())
    if (
        not normalized
        or len(normalized) > 16000
        or any(ord(char) < 32 for char in normalized)
    ):
        raise MessageValidationError()
    return normalized


def _address(value: Any) -> str | None:
    if isinstance(value, Mapping):
        email = value.get("emailAddress")
        if isinstance(email, Mapping) and isinstance(email.get("address"), str):
            return email["address"].casefold()
    return None


def evidence_from_message(
    entity: Mapping[str, Any],
    *,
    location: MessageLocation | None,
    binding: SourceBinding,
    case_id: str,
    analysis_id: str,
    retrieved_at: datetime,
) -> EvidenceItem:
    if location is None or not location.within(binding):
        raise MessageValidationError()
    expected_id = (
        binding.supplier_source_id
        if location.source_kind == "supplier"
        else binding.quality_source_id
    )
    if (
        entity.get("id") != location.message_id
        or location.message_id != expected_id
        or entity.get("deletedDateTime") is not None
        or "@removed" in entity
    ):
        raise MessageValidationError()
    if location.source_kind == "supplier":
        if _address(entity.get("sender")) != binding.supplier_sender.casefold():
            raise MessageValidationError()
        if (
            "from" in entity
            and _address(entity["from"]) != binding.supplier_sender.casefold()
        ):
            raise MessageValidationError()
        timestamp = entity.get("receivedDateTime")
        scope = AuthorityScope.SUPPLIER_STATEMENT
        link_keys = ("webLink", "sourceUrl")
    else:
        sender, channel = entity.get("from"), entity.get("channelIdentity")
        user = sender.get("user") if isinstance(sender, Mapping) else None
        if (
            not isinstance(user, Mapping)
            or user.get("id") != binding.quality_author_object_id
            or not isinstance(channel, Mapping)
            or channel.get("teamId") != location.team_id
            or channel.get("channelId") != location.channel_id
        ):
            raise MessageValidationError()
        timestamp = entity.get("createdDateTime")
        scope = AuthorityScope.COLLABORATION_STATEMENT
        link_keys = ("webUrl", "sourceUrl")
    if not isinstance(timestamp, str):
        raise MessageValidationError()
    try:
        source_timestamp = datetime.fromisoformat(timestamp)
    except ValueError:
        raise MessageValidationError() from None
    if source_timestamp.utcoffset() is None:
        raise MessageValidationError()
    links = [entity[key] for key in link_keys if key in entity]
    if not links:
        raise MessageValidationError()
    for link in links:
        linked = parse_location(link)
        if (
            not isinstance(link, str)
            or not link.startswith("https://")
            or linked is None
            or not location.same_message(linked, binding)
        ):
            raise MessageValidationError()
    text = _text(entity.get("body"))
    return EvidenceItem(
        evidence_id=f"workiq-{uuid4().hex}",
        case_id=case_id,
        kind=EvidenceKind.SOURCE_STATEMENT,
        authority_scope=(scope,),
        source_system=EvidenceSourceSystem.WORK_IQ,
        source_id=entity["id"],
        source_timestamp=source_timestamp,
        retrieved_at=retrieved_at,
        retrieved_for_analysis_id=analysis_id,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=None,
        expires_at=None,
        claim=text,
        excerpt=text,
        citation_url=links[0],
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
        requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
        uncertainty_state=UncertaintyState.CERTAIN,
    )
