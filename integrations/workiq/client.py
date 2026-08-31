from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final
from uuid import uuid4

import httpx

from apps.api.app.auth import UserAssertion
from data.domain.evidence import EvidenceItem

from .normalizer import normalize_a2a_evidence
from .obo import WorkIQOboExchange
from .prompts import quality_context_prompt, supplier_signal_prompt
from .errors import WorkIQProtocolError, WorkIQResponseLimitError

WORK_IQ_A2A_ENDPOINT: Final = "https://workiq.svc.cloud.microsoft/a2a/"
_MAX_RESPONSE_BYTES: Final = 1_048_576
_MAX_JSON_DEPTH: Final = 12
_MAX_CONTAINER_ITEMS: Final = 256
_MAX_ARTIFACTS: Final = 64
_MAX_PARTS_PER_ARTIFACT: Final = 32
_MAX_TEXT_CHARS: Final = 32_768


def _validate_json_bounds(value: Any, *, depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH:
        raise WorkIQResponseLimitError("Work IQ response exceeds JSON depth limit")
    if isinstance(value, str):
        if len(value) > _MAX_TEXT_CHARS:
            raise WorkIQResponseLimitError("Work IQ response text exceeds size limit")
    elif isinstance(value, Mapping):
        if len(value) > _MAX_CONTAINER_ITEMS:
            raise WorkIQResponseLimitError("Work IQ response object exceeds item limit")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 256:
                raise WorkIQResponseLimitError("Work IQ response key is invalid")
            _validate_json_bounds(item, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > _MAX_CONTAINER_ITEMS:
            raise WorkIQResponseLimitError("Work IQ response array exceeds item limit")
        for item in value:
            _validate_json_bounds(item, depth=depth + 1)


def _validate_artifact_bounds(result: Mapping[str, Any]) -> None:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > _MAX_ARTIFACTS:
        raise WorkIQResponseLimitError("Work IQ artifact count is invalid")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise WorkIQProtocolError("Work IQ artifact is malformed")
        parts = artifact.get("parts")
        if not isinstance(parts, list) or len(parts) > _MAX_PARTS_PER_ARTIFACT:
            raise WorkIQResponseLimitError("Work IQ artifact part count is invalid")


class WorkIQClient:
    def __init__(self, *, http: httpx.AsyncClient) -> None:
        self._http = http

    async def send_message(self, prompt: str, *, access_token: str) -> dict[str, Any]:
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt) > _MAX_TEXT_CHARS
        ):
            raise ValueError("Work IQ prompt is invalid")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("Work IQ access token is missing")
        request_id = str(uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "SendMessage",
            "params": {
                "message": {
                    "role": "ROLE_USER",
                    "messageId": str(uuid4()),
                    "parts": [{"text": prompt}],
                    "metadata": {
                        "Location": {
                            "timeZoneOffset": -300,
                            "timeZone": "America/Chicago",
                        }
                    },
                }
            },
        }
        try:
            async with self._http.stream(
                "POST",
                WORK_IQ_A2A_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "A2A-Version": "1.0",
                },
                json=payload,
                timeout=30.0,
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise WorkIQProtocolError(
                        f"Work IQ returned HTTP {response.status_code}"
                    )
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES:
                        raise WorkIQResponseLimitError(
                            "Work IQ response exceeds byte limit"
                        )
                    chunks.append(chunk)
        except WorkIQProtocolError:
            raise
        except httpx.HTTPError as error:
            raise WorkIQProtocolError("Work IQ request failed") from error
        try:
            document = json.loads(b"".join(chunks))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            raise WorkIQProtocolError("Work IQ returned malformed JSON") from error
        if not isinstance(document, dict):
            raise WorkIQProtocolError("Work IQ response must be a JSON object")
        _validate_json_bounds(document)
        if (
            document.get("jsonrpc") != "2.0"
            or document.get("id") != request_id
            or "error" in document
        ):
            raise WorkIQProtocolError("Work IQ JSON-RPC envelope is invalid")
        result = document.get("result")
        if not isinstance(result, Mapping):
            raise WorkIQProtocolError("Work IQ result is missing")
        status = result.get("status")
        if (
            not isinstance(status, Mapping)
            or status.get("state") != "TASK_STATE_COMPLETED"
        ):
            raise WorkIQProtocolError("Work IQ task did not complete")
        _validate_artifact_bounds(result)
        return document


class WorkIQEvidencePort:
    """Application-facing adapter that exposes only normalized evidence."""

    def __init__(self, *, client: WorkIQClient, obo: WorkIQOboExchange) -> None:
        self._client = client
        self._obo = obo

    async def retrieve_supplier_signal(
        self,
        *,
        assertion: UserAssertion,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: Any,
    ) -> tuple[EvidenceItem, ...]:
        token = self._obo.exchange(assertion)
        payload = await self._client.send_message(
            supplier_signal_prompt(source_id), access_token=token.reveal()
        )
        return normalize_a2a_evidence(
            payload,
            case_id=case_id,
            analysis_id=analysis_id,
            retrieved_at=retrieved_at,
        )

    async def retrieve_quality_context(
        self,
        *,
        assertion: UserAssertion,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: Any,
    ) -> tuple[EvidenceItem, ...]:
        token = self._obo.exchange(assertion)
        payload = await self._client.send_message(
            quality_context_prompt(source_id), access_token=token.reveal()
        )
        return normalize_a2a_evidence(
            payload,
            case_id=case_id,
            analysis_id=analysis_id,
            retrieved_at=retrieved_at,
        )
