"""Bounded, read-only discovery of reviewable supplier inbox messages."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Final, Protocol
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

from data.domain.evidence import EvidenceItem
from data.domain.inbound import (
    InboundEmailError,
    SupplierDisruptionFacts,
    SupplierEmailSource,
    parse_supplier_disruption,
)

from .locations import parse_location
from .message_evidence import MessageValidationError, evidence_from_message
from .models import SourceBinding

SUBJECT_MARKERS: Final = ("[Supply Response Demo]", "RL-001", "Supplier Alpha")
BODY_MARKER: Final = "RL-MAT-10247"
SUPPLIER_SENDER: Final = "will@willmacdonald.com"
RECIPIENT: Final = "agent@willmacdonald.com"
MAX_COLLECTION: Final = 25
MAX_BODY_READS: Final = 5
_SEARCH = quote('"subject:RL-001"', safe="")
INBOX_QUERY: Final = (
    f"/me/messages?$search={_SEARCH}&$top={MAX_COLLECTION}&"
    "$select=id,subject,sender,from,toRecipients,receivedDateTime"
)


class InboxMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    subject: str
    sender: str
    received_at: datetime
    excerpt: str
    citation_url: str
    internet_message_id: str | None = None
    review_fingerprint: str | None = None
    facts: SupplierDisruptionFacts | None = None
    creation_blocker: str | None = None


class InboxCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checked_at: datetime
    messages: list[InboxMessage]
    incomplete: bool


class FetchSession(Protocol):
    async def fetch(self, entity_url: str) -> dict[str, object]: ...


def _address(value: object) -> str | None:
    if isinstance(value, Mapping):
        email = value.get("emailAddress")
        if isinstance(email, Mapping) and isinstance(email.get("address"), str):
            return email["address"].casefold()
    return None


def _recipients(value: object) -> set[str] | None:
    if not isinstance(value, list) or not value:
        return None
    addresses = {_address(item) for item in value}
    if None in addresses:
        return None
    return {address for address in addresses if address is not None}


def _metadata_candidate(row: Mapping[str, Any]) -> bool:
    subject = row.get("subject")
    received = row.get("receivedDateTime")
    if not isinstance(subject, str) or not isinstance(received, str):
        raise TypeError("invalid inbox metadata")
    parsed = datetime.fromisoformat(received)
    if parsed.utcoffset() is None:
        raise ValueError("invalid inbox metadata")
    recipients = _recipients(row.get("toRecipients"))
    if recipients is None:
        raise ValueError("invalid inbox metadata")
    return (
        all(marker in subject for marker in SUBJECT_MARKERS)
        and _address(row.get("sender")) == SUPPLIER_SENDER.casefold()
        and _address(row.get("from")) == SUPPLIER_SENDER.casefold()
        and RECIPIENT.casefold() in recipients
    )


def _entity_data(payload: object) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("invalid inbox entity")
    results = payload.get("results")
    if (
        not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], Mapping)
        or results[0].get("statusCode") != 200
        or not isinstance(results[0].get("data"), Mapping)
    ):
        raise ValueError("invalid inbox entity")
    return results[0]["data"]


def _identity(value: object) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(
            r"<[^\s<>\x00-\x1f\x7f]{1,994}@[^\s<>\x00-\x1f\x7f]+>", value
        )
        or len(value) > 998
    ):
        raise InboundEmailError("INBOUND_EMAIL_UNAVAILABLE")
    return value


def _fingerprint(
    entity: Mapping[str, Any], evidence: EvidenceItem, binding: SourceBinding
) -> str:
    # Provider locator and link may change on a folder move; content and mailbox may not.
    assert evidence.source_timestamp is not None
    values = {
        "tenant": binding.tenant_id,
        "mailbox": binding.alex_object_id,
        "identity": _identity(entity.get("internetMessageId")),
        "subject": entity["subject"],
        "sender": _address(entity.get("sender")),
        "from": _address(entity.get("from")),
        "recipients": sorted(_recipients(entity.get("toRecipients")) or ()),
        "received": evidence.source_timestamp.astimezone(UTC).isoformat(),
        "body": evidence.claim,
    }
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def review_email(
    session: FetchSession,
    *,
    binding: SourceBinding,
    internet_message_id: str,
    review_fingerprint: str,
    checked_at: datetime,
    case_id: str = "inbox-review",
    analysis_id: str = "inbox-review",
) -> tuple[SupplierEmailSource, EvidenceItem]:
    """Resolve an Internet Message-ID in the bound mailbox and revalidate its entity."""
    identity = _identity(internet_message_id)
    escaped = identity.replace("'", "''")
    query = quote(f"internetMessageId eq '{escaped}'", safe="")
    data = _entity_data(
        await session.fetch(
            f"/me/messages?$filter={query}&$top={MAX_BODY_READS + 1}&"
            "$select=id,internetMessageId,subject,sender,from,toRecipients,receivedDateTime"
        )
    )
    rows = data.get("value")
    if (
        not isinstance(rows, list)
        or not rows
        or "@odata.nextLink" in data
        or "nextLink" in data
    ):
        raise InboundEmailError("INBOUND_EMAIL_UNAVAILABLE")
    if len(rows) != 1:
        raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
    row = rows[0]
    try:
        if (
            not isinstance(row, Mapping)
            or row.get("internetMessageId") != identity
            or not _metadata_candidate(row)
        ):
            raise ValueError()
        locator = row.get("id")
        if not isinstance(locator, str):
            raise TypeError()
        location = parse_location(f"/me/messages/{quote(locator, safe='')}")
        if location is None:
            raise ValueError()
        entity = _entity_data(await session.fetch(location.fetch_path))
        if entity.get("internetMessageId") != identity or not _metadata_candidate(
            entity
        ):
            raise ValueError()
        dynamic = replace(
            binding, supplier_source_id=locator, supplier_sender=SUPPLIER_SENDER
        )
        evidence = evidence_from_message(
            entity,
            location=location,
            binding=dynamic,
            case_id=case_id,
            analysis_id=analysis_id,
            retrieved_at=checked_at,
        )
        if BODY_MARKER not in evidence.claim:
            raise ValueError()
    except (ValueError, TypeError, MessageValidationError):
        raise InboundEmailError("INBOUND_EMAIL_CONFLICT") from None
    fingerprint = _fingerprint(entity, evidence, binding)
    if fingerprint != review_fingerprint:
        raise InboundEmailError("INBOUND_EMAIL_CHANGED")
    facts = parse_supplier_disruption(evidence.claim)
    assert evidence.source_timestamp is not None and evidence.citation_url is not None
    return SupplierEmailSource(
        tenant_id=binding.tenant_id,
        mailbox_object_id=binding.alex_object_id,
        internet_message_id=identity,
        review_fingerprint=fingerprint,
        message_id=locator,
        subject=entity["subject"],
        sender=SUPPLIER_SENDER,
        recipients=tuple(sorted(_recipients(entity["toRecipients"]) or ())),
        received_at=evidence.source_timestamp,
        reviewed_at=checked_at,
        citation_url=evidence.citation_url,
        facts=facts,
    ), evidence


async def discover_inbox(
    session: FetchSession, *, binding: SourceBinding, checked_at: datetime
) -> InboxCheck:
    """Search one bounded collection and validate at most five returned messages."""
    payload = await session.fetch(INBOX_QUERY)
    data = _entity_data(payload)
    rows = data.get("value")
    if not isinstance(rows, list):
        raise TypeError("invalid inbox collection")
    incomplete = "@odata.nextLink" in data or "nextLink" in data
    if len(rows) > MAX_COLLECTION:
        return InboxCheck(checked_at=checked_at, messages=[], incomplete=True)

    candidates: list[tuple[str, Mapping[str, Any]]] = []
    identities: set[str] = set()
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            incomplete = True
            continue
        identity = raw_row.get("id")
        if not isinstance(identity, str):
            incomplete = True
            continue
        location = parse_location(f"/me/messages/{quote(identity, safe='')}")
        if location is None or identity in identities:
            incomplete = True
            continue
        identities.add(identity)
        try:
            if _metadata_candidate(raw_row):
                candidates.append((identity, raw_row))
        except (TypeError, ValueError):
            incomplete = True

    if len(candidates) > MAX_BODY_READS:
        incomplete = True
    messages: list[InboxMessage] = []
    for identity, _row in candidates[:MAX_BODY_READS]:
        location = parse_location(f"/me/messages/{quote(identity, safe='')}")
        assert location is not None
        entity: Mapping[str, Any] | None = None
        try:
            entity = _entity_data(await session.fetch(location.fetch_path))
            subject = entity.get("subject")
            recipients = _recipients(entity.get("toRecipients"))
            if (
                not isinstance(subject, str)
                or not all(marker in subject for marker in SUBJECT_MARKERS)
                or recipients is None
                or RECIPIENT.casefold() not in recipients
            ):
                raise MessageValidationError()
            dynamic_binding = replace(
                binding,
                supplier_sender=SUPPLIER_SENDER,
                supplier_source_id=identity,
            )
            evidence = evidence_from_message(
                entity,
                location=location,
                binding=dynamic_binding,
                case_id="inbox-check",
                analysis_id="inbox-check",
                retrieved_at=checked_at,
            )
            if BODY_MARKER not in evidence.claim:
                raise MessageValidationError()
            assert evidence.source_timestamp is not None
            assert evidence.citation_url is not None and evidence.excerpt is not None
            identity_value = fingerprint = facts = blocker = None
            try:
                identity_value = _identity(entity.get("internetMessageId"))
                fingerprint = _fingerprint(entity, evidence, binding)
                facts = parse_supplier_disruption(evidence.claim)
            except InboundEmailError as error:
                blocker = error.code
            messages.append(
                InboxMessage(
                    message_id=identity,
                    subject=subject,
                    sender=dynamic_binding.supplier_sender,
                    received_at=evidence.source_timestamp,
                    excerpt=evidence.excerpt[:4000]
                    + ("…" if len(evidence.excerpt) > 4000 else ""),
                    citation_url=evidence.citation_url,
                    internet_message_id=identity_value,
                    review_fingerprint=fingerprint,
                    facts=facts,
                    creation_blocker=blocker,
                )
            )
        except Exception:  # noqa: BLE001 - an invalid candidate makes the scan partial
            incomplete = True
        finally:
            entity = None
    return InboxCheck(checked_at=checked_at, messages=messages, incomplete=incomplete)
