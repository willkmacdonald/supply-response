"""Bounded, read-only discovery of reviewable supplier inbox messages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any, Final, Protocol
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

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
            messages.append(
                InboxMessage(
                    message_id=identity,
                    subject=subject,
                    sender=dynamic_binding.supplier_sender,
                    received_at=evidence.source_timestamp,
                    excerpt=evidence.excerpt[:4000]
                    + ("…" if len(evidence.excerpt) > 4000 else ""),
                    citation_url=evidence.citation_url,
                )
            )
        except Exception:  # noqa: BLE001 - an invalid candidate makes the scan partial
            incomplete = True
        finally:
            entity = None
    return InboxCheck(checked_at=checked_at, messages=messages, incomplete=incomplete)
