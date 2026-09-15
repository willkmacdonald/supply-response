"""Small allowlisted Microsoft Graph mail adapter."""

from __future__ import annotations

import asyncio
import json as stdlib_json
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol
from urllib.parse import quote

import httpx

from data.domain.outbound_mail import SupplierEmailRevision
from integrations.graph_mail.obo import GraphAccessToken

_GRAPH_ROOT: Final = "https://graph.microsoft.com/v1.0"
_PREFER: Final = 'IdType="ImmutableId", outlook.body-content-type="text"'
_MAX_RESPONSE_BYTES: Final = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS: Final = 12
_SAFE_CODES: Final = frozenset(
    {
        "graph_authentication_failed",
        "graph_capability_failed",
        "graph_create_failed",
        "graph_get_failed",
        "graph_message_mismatch",
        "graph_response_invalid",
        "graph_send_failed",
        "graph_send_uncertain",
    }
)


class GraphMailError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code if code in _SAFE_CODES else "graph_response_invalid"
        super().__init__(self.code)


class GraphMailSubmissionUncertain(GraphMailError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderDraft:
    provider_message_id: str
    internet_message_id: str | None


@dataclass(frozen=True, slots=True)
class ProviderMessage:
    provider_message_id: str
    internet_message_id: str | None
    sender_address: str
    to_addresses: tuple[str, ...]
    subject: str
    body_content_type: str
    body: str
    sent_at: datetime | None


@dataclass(frozen=True, slots=True)
class GraphMailCapability:
    mailbox_address: str
    sample_sent_message_id: str


class GraphTokenPort(Protocol):
    async def exchange(self, actor: object) -> GraphAccessToken: ...


class GraphMailPort(Protocol):
    async def capability(self, actor: object) -> GraphMailCapability: ...

    async def create_draft(
        self, revision: SupplierEmailRevision, actor: object
    ) -> ProviderDraft: ...

    async def send_draft(self, provider_message_id: str, actor: object) -> None: ...

    async def get_message(
        self, provider_message_id: str, actor: object
    ) -> ProviderMessage: ...


class GraphMailClient:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        obo: GraphTokenPort,
        mailbox_address: str,
    ) -> None:
        if http.follow_redirects:
            raise ValueError("Graph mail client must not follow redirects")
        if mailbox_address != mailbox_address.lower() or not _valid_address(
            mailbox_address
        ):
            raise ValueError("Graph mailbox address is invalid")
        self._http = http
        self._obo = obo
        self._mailbox_address = mailbox_address

    async def _headers(self, actor: object) -> dict[str, str]:
        try:
            token = await self._obo.exchange(actor)
        except Exception:  # noqa: BLE001 - hide identity-provider details
            raise GraphMailError("graph_authentication_failed") from None
        if not isinstance(token, GraphAccessToken):
            raise GraphMailError("graph_authentication_failed")
        return {
            "Authorization": f"Bearer {token.reveal()}",
            "Accept": "application/json",
            "Prefer": _PREFER,
        }

    async def _request(
        self,
        method: str,
        path: str,
        actor: object,
        *,
        failure_code: str,
        json: dict[str, object] | None = None,
        expect_json: bool = True,
        expected_statuses: frozenset[int] = frozenset({200}),
        uncertain_after_submit: bool = False,
    ) -> dict[str, object] | None:
        headers = await self._headers(actor)
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT_SECONDS):
                async with self._http.stream(
                    method,
                    f"{_GRAPH_ROOT}{path}",
                    headers=headers,
                    json=json,
                ) as response:
                    if (
                        response.is_redirect
                        or response.status_code not in expected_statuses
                    ):
                        if uncertain_after_submit and response.status_code >= 500:
                            raise GraphMailSubmissionUncertain("graph_send_uncertain")
                        raise GraphMailError(failure_code)
                    content_length = response.headers.get("content-length")
                    if (
                        content_length is not None
                        and content_length.isdigit()
                        and int(content_length) > _MAX_RESPONSE_BYTES
                    ):
                        if uncertain_after_submit:
                            raise GraphMailSubmissionUncertain("graph_send_uncertain")
                        raise GraphMailError("graph_response_invalid")
                    if expect_json and not _json_media_type(
                        response.headers.get("content-type", "")
                    ):
                        raise GraphMailError("graph_response_invalid")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                            if uncertain_after_submit:
                                raise GraphMailSubmissionUncertain(
                                    "graph_send_uncertain"
                                )
                            raise GraphMailError("graph_response_invalid")
                        body.extend(chunk)
        except (TimeoutError, httpx.TransportError):
            if uncertain_after_submit:
                raise GraphMailSubmissionUncertain("graph_send_uncertain") from None
            raise GraphMailError(failure_code) from None
        if not expect_json:
            if body:
                raise GraphMailSubmissionUncertain("graph_send_uncertain")
            return None
        try:
            value = stdlib_json.loads(body)
        except (stdlib_json.JSONDecodeError, UnicodeDecodeError):
            raise GraphMailError("graph_response_invalid") from None
        if not isinstance(value, dict):
            raise GraphMailError("graph_response_invalid")
        return value

    async def capability(self, actor: object) -> GraphMailCapability:
        sent = await self._request(
            "GET",
            "/me/mailFolders/sentitems/messages?$select=id&$top=1&$orderby=sentDateTime%20desc",
            actor,
            failure_code="graph_capability_failed",
        )
        assert sent is not None
        values = sent.get("value")
        item = values[0] if isinstance(values, list) and len(values) == 1 else None
        message_id = item.get("id") if isinstance(item, dict) else None
        safe_id = _message_id(message_id)
        exact = await self._request(
            "GET",
            f"/me/messages/{quote(safe_id, safe='')}?$select=id,sender,from",
            actor,
            failure_code="graph_capability_failed",
        )
        if exact is None or exact.get("id") != safe_id:
            raise GraphMailError("graph_capability_failed")
        try:
            sender = _address(exact.get("sender"))
            from_address = _address(exact.get("from"))
        except GraphMailError:
            raise GraphMailError("graph_capability_failed") from None
        if sender != from_address or sender != self._mailbox_address:
            raise GraphMailError("graph_capability_failed")
        return GraphMailCapability(
            mailbox_address=self._mailbox_address,
            sample_sent_message_id=safe_id,
        )

    async def create_draft(
        self, revision: SupplierEmailRevision, actor: object
    ) -> ProviderDraft:
        payload: dict[str, object] = {
            "subject": revision.subject,
            "body": {"contentType": "Text", "content": revision.body},
            "toRecipients": [{"emailAddress": {"address": revision.to_address}}],
        }
        created = await self._request(
            "POST",
            "/me/messages",
            actor,
            json=payload,
            failure_code="graph_create_failed",
            expected_statuses=frozenset({201}),
        )
        assert created is not None
        provider_id = _message_id(created.get("id"))
        message = await self.get_message(provider_id, actor)
        if not _matches_revision(message, revision, self._mailbox_address):
            raise GraphMailError("graph_message_mismatch")
        return ProviderDraft(
            provider_message_id=provider_id,
            internet_message_id=message.internet_message_id,
        )

    async def send_draft(self, provider_message_id: str, actor: object) -> None:
        safe_id = _message_id(provider_message_id)
        await self._request(
            "POST",
            f"/me/messages/{quote(safe_id, safe='')}/send",
            actor,
            failure_code="graph_send_failed",
            expect_json=False,
            expected_statuses=frozenset({202}),
            uncertain_after_submit=True,
        )

    async def get_message(
        self, provider_message_id: str, actor: object
    ) -> ProviderMessage:
        safe_id = _message_id(provider_message_id)
        value = await self._request(
            "GET",
            (
                f"/me/messages/{quote(safe_id, safe='')}"
                "?$select=id,internetMessageId,subject,body,from,sender,toRecipients,sentDateTime"
            ),
            actor,
            failure_code="graph_get_failed",
        )
        assert value is not None
        return _provider_message(value, safe_id)


def _valid_address(value: str) -> bool:
    local, separator, domain = value.partition("@")
    return bool(separator and local and domain and not any(c.isspace() for c in value))


def _json_media_type(value: str) -> bool:
    media_type = value.partition(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _message_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(character) < 33 for character in value)
    ):
        raise GraphMailError("graph_response_invalid")
    return value


def _address(value: object) -> str:
    if not isinstance(value, dict):
        raise GraphMailError("graph_response_invalid")
    email = value.get("emailAddress")
    address = email.get("address") if isinstance(email, dict) else None
    if not isinstance(address, str) or not _valid_address(address):
        raise GraphMailError("graph_response_invalid")
    return address.lower()


def _provider_message(value: dict[str, object], expected_id: str) -> ProviderMessage:
    if value.get("id") != expected_id:
        raise GraphMailError("graph_response_invalid")
    sender_address = _address(value.get("sender"))
    from_address = _address(value.get("from"))
    if sender_address != from_address:
        raise GraphMailError("graph_response_invalid")
    recipients = value.get("toRecipients")
    body = value.get("body")
    subject = value.get("subject")
    content_type = body.get("contentType") if isinstance(body, dict) else None
    content = body.get("content") if isinstance(body, dict) else None
    if (
        not isinstance(recipients, list)
        or not isinstance(body, dict)
        or not isinstance(subject, str)
        or not isinstance(content_type, str)
        or not isinstance(content, str)
    ):
        raise GraphMailError("graph_response_invalid")
    sent_raw = value.get("sentDateTime")
    try:
        sent_at = (
            datetime.fromisoformat(sent_raw)
            if isinstance(sent_raw, str) and sent_raw
            else None
        )
    except ValueError:
        raise GraphMailError("graph_response_invalid") from None
    internet_id = value.get("internetMessageId")
    if internet_id is not None and not isinstance(internet_id, str):
        raise GraphMailError("graph_response_invalid")
    return ProviderMessage(
        provider_message_id=expected_id,
        internet_message_id=internet_id,
        sender_address=sender_address,
        to_addresses=tuple(_address(item) for item in recipients),
        subject=subject,
        body_content_type=content_type.lower(),
        body=content,
        sent_at=sent_at,
    )


def _matches_revision(
    message: ProviderMessage,
    revision: SupplierEmailRevision,
    mailbox_address: str,
) -> bool:
    return (
        message.sender_address == mailbox_address == revision.from_address
        and message.to_addresses == (revision.to_address,)
        and message.subject == revision.subject
        and message.body_content_type == "text"
        and message.body == revision.body
    )
