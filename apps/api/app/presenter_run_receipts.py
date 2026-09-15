"""Authenticated, source-bound Presenter Run receipts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Iterable
from typing import Final

from data.domain.cases import PRESENTER_RUN_PATTERN

_VERSION: Final = "PRR1"
_KEY_CONTEXT: Final = b"supply-response:presenter-run-receipt:key:v1"
_SIGNATURE_CONTEXT: Final = b"supply-response:presenter-run-receipt:signature:v1"
_SOURCE_CONTEXT: Final = b"supply-response:presenter-run-receipt:source:v1"
_TOKEN_SEGMENT: Final = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256_HEX: Final = re.compile(r"^[0-9a-f]{64}$")
_MAX_AUTHORIZED_SOURCES: Final = 16


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _signing_key(client_secret: str | None) -> bytes:
    if not isinstance(client_secret, str) or not client_secret:
        raise ValueError("Presenter Run signing key is unavailable")
    return hmac.digest(client_secret.encode(), _KEY_CONTEXT, hashlib.sha256)


def _source_hash(
    signing_key: bytes,
    internet_message_id: str,
    review_fingerprint: str,
) -> str:
    source = _canonical_json([internet_message_id, review_fingerprint])
    return hmac.digest(
        signing_key,
        _SOURCE_CONTEXT + b"\0" + source,
        hashlib.sha256,
    ).hex()


def _signature(
    signing_key: bytes,
    payload: bytes,
    *,
    tenant_id: str,
    object_id: str,
) -> bytes:
    actor = _canonical_json([tenant_id, object_id])
    return hmac.digest(
        signing_key,
        _SIGNATURE_CONTEXT + b"\0" + actor + b"\0" + payload,
        hashlib.sha256,
    )


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not _TOKEN_SEGMENT.fullmatch(value):
        raise ValueError("invalid receipt encoding")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _encode(decoded) != value:
        raise ValueError("non-canonical receipt encoding")
    return decoded


def issue_presenter_run_receipt(
    client_secret: str | None,
    *,
    tenant_id: str,
    object_id: str,
    presenter_run_id: str,
    allowed_sources: Iterable[tuple[str, str]],
) -> str:
    """Issue a receipt for one actor, run, and set of reviewed source identities."""
    if re.fullmatch(PRESENTER_RUN_PATTERN, presenter_run_id) is None:
        raise ValueError("invalid Presenter Run identifier")
    signing_key = _signing_key(client_secret)
    source_hashes = sorted(
        {
            _source_hash(signing_key, internet_message_id, review_fingerprint)
            for internet_message_id, review_fingerprint in allowed_sources
        }
    )
    if len(source_hashes) > _MAX_AUTHORIZED_SOURCES:
        raise ValueError("too many Presenter Run sources")
    payload = _canonical_json(
        {
            "presenter_run_id": presenter_run_id,
            "source_hashes": source_hashes,
        }
    )
    signature = _signature(
        signing_key,
        payload,
        tenant_id=tenant_id,
        object_id=object_id,
    )
    return f"{_VERSION}.{_encode(payload)}.{_encode(signature)}"


def verify_presenter_run_receipt(
    receipt: str,
    client_secret: str | None,
    *,
    tenant_id: str,
    object_id: str,
    presenter_run_id: str,
    internet_message_id: str,
    review_fingerprint: str,
) -> bool:
    """Fail closed unless the receipt authorizes this actor, run, and source."""
    try:
        version, encoded_payload, encoded_signature = receipt.split(".")
        if version != _VERSION:
            return False
        payload = _decode(encoded_payload)
        supplied_signature = _decode(encoded_signature)
        signing_key = _signing_key(client_secret)
        expected_signature = _signature(
            signing_key,
            payload,
            tenant_id=tenant_id,
            object_id=object_id,
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return False
        decoded = json.loads(payload)
        if not isinstance(decoded, dict) or set(decoded) != {
            "presenter_run_id",
            "source_hashes",
        }:
            return False
        signed_run_id = decoded["presenter_run_id"]
        source_hashes = decoded["source_hashes"]
        if (
            not isinstance(signed_run_id, str)
            or re.fullmatch(PRESENTER_RUN_PATTERN, signed_run_id) is None
            or signed_run_id != presenter_run_id
            or not isinstance(source_hashes, list)
            or len(source_hashes) > _MAX_AUTHORIZED_SOURCES
            or source_hashes != sorted(set(source_hashes))
            or any(
                not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None
                for value in source_hashes
            )
        ):
            return False
        expected_source = _source_hash(
            signing_key,
            internet_message_id,
            review_fingerprint,
        )
        return any(
            hmac.compare_digest(expected_source, source_hash)
            for source_hash in source_hashes
        )
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return False
