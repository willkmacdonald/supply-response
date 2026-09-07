"""Strict individual-message locators. No configured message identity is an input."""

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from .models import SourceBinding, SourceKind


@dataclass(frozen=True, slots=True)
class MessageLocation:
    source_kind: SourceKind
    message_id: str
    mailbox: str | None = None
    team_id: str | None = None
    channel_id: str | None = None
    tenant_id: str | None = None

    @property
    def fetch_path(self) -> str:
        if self.source_kind == "supplier":
            parts = ["me"] if self.mailbox == "me" else ["users", self.mailbox]
            parts += ["messages", self.message_id]
        else:
            parts = [
                "teams",
                self.team_id,
                "channels",
                self.channel_id,
                "messages",
                self.message_id,
            ]
        return "/" + "/".join(
            quote(part, safe="") for part in parts if part is not None
        )

    def within(self, binding: SourceBinding) -> bool:
        if self.tenant_id is not None and self.tenant_id != binding.tenant_id:
            return False
        if self.source_kind == "supplier":
            return self.mailbox in ("me", binding.alex_object_id)
        return self.team_id == binding.team_id and self.channel_id == binding.channel_id

    def same_message(self, other: "MessageLocation", binding: SourceBinding) -> bool:
        return (
            self.within(binding)
            and other.within(binding)
            and self.source_kind == other.source_kind
            and self.message_id == other.message_id
        )


def _identity(value: str) -> str:
    # Opaque identities stay case-sensitive. Reject repeated encoding and separators
    # instead of allowing URL parsers or the upstream service to reinterpret them.
    if not re.fullmatch(r"[A-Za-z0-9_+@=:.!~-]{1,2048}", value) or value in (".", ".."):
        raise ValueError("Unsupported identity")
    return value


def parse_location(value: object) -> MessageLocation | None:
    if (
        not isinstance(value, str)
        or len(value) > 8192
        or any(char.isspace() or ord(char) < 32 for char in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            return None
        if re.search(r"%(?![0-9a-fA-F]{2})", value):
            return None
        parts = [
            _identity(unquote(p, errors="strict"))
            for p in parsed.path.split("/")[1:]
            if p
        ]
        if "//" in parsed.path or (
            parsed.path.endswith("/") and parsed.path != "/owa/"
        ):
            return None
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        query = dict(pairs)
        if len(query) != len(pairs):
            return None
        if (
            not parsed.scheme
            and not parsed.netloc
            and not query
            and parsed.path.startswith("/")
        ):
            match parts:
                case ["me", "messages", message]:
                    return MessageLocation("supplier", message, mailbox="me")
                case ["users", mailbox, "messages", message]:
                    return MessageLocation("supplier", message, mailbox=mailbox)
                case ["teams", team, "channels", channel, "messages", message]:
                    return MessageLocation(
                        "quality", message, team_id=team, channel_id=channel
                    )
            return None
        if parsed.scheme != "https":
            return None
        if parsed.hostname in ("outlook.office.com", "outlook.office365.com"):
            if (
                len(parts) == 4
                and parts[:3] == ["mail", "deeplink", "read"]
                and not query
            ):
                return MessageLocation("supplier", parts[3], mailbox="me")
            if (
                parts == ["owa"]
                and query.keys() <= {"ItemID", "exvsurl", "viewmodel"}
                and query.get("viewmodel") == "ReadMessageItem"
                and query.get("exvsurl", "1") == "1"
            ):
                return MessageLocation(
                    "supplier", _identity(query["ItemID"]), mailbox="me"
                )
        if (
            parsed.hostname == "teams.microsoft.com"
            and len(parts) == 4
            and parts[:2] == ["l", "message"]
        ):
            if not query.keys() <= {
                "groupId",
                "tenantId",
                "parentMessageId",
                "createdTime",
            }:
                return None
            team, tenant = _identity(query["groupId"]), _identity(query["tenantId"])
            if query.get("parentMessageId", parts[3]) != parts[3]:
                return None
            if "createdTime" in query and not re.fullmatch(
                r"[0-9]{1,20}", query["createdTime"]
            ):
                return None
            return MessageLocation(
                "quality", parts[3], team_id=team, channel_id=parts[2], tenant_id=tenant
            )
    except (ValueError, KeyError, UnicodeError):
        return None
    return None
