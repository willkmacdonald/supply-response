"""MSAL's synchronous HTTP interface backed by cancellable, bounded async I/O."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
import time
from typing import Any
from uuid import UUID

import httpx
from opentelemetry.instrumentation.utils import suppress_instrumentation

from .errors import WorkIQProtocolError
from .mcp import MAX_RESPONSE_BYTES, bounded_json
from .obo import _AAD_CODES, _OAUTH_ERRORS, WORK_IQ_SCOPE, WorkIQAuthenticationError


class _SafeResponse:
    """Expose only sanitized JSON to MSAL, whose invalid-JSON log includes text."""

    def __init__(self, status: int, value: dict[str, Any]) -> None:
        self.status_code = status
        self.text = json.dumps(value)
        self.headers: dict[str, str] = {}

    def __repr__(self) -> str:
        return "WorkIQOboResponse(<redacted>)"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise WorkIQAuthenticationError("Work IQ identity request failed")


def _token_result(value: dict[str, Any]) -> dict[str, Any]:
    if "error" in value:
        code = value["error"]
        codes = value.get("error_codes")
        return {
            "error": code
            if isinstance(code, str) and code in _OAUTH_ERRORS
            else "unknown",
            "error_codes": [c for c in codes if type(c) is int and c in _AAD_CODES][:1]
            if isinstance(codes, list)
            else [],
        }
    token, scope = value.get("access_token"), value.get("scope")
    allowed_scopes = {
        WORK_IQ_SCOPE,
        "WorkIQAgent.Ask",
        "openid",
        "profile",
        "offline_access",
    }
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= 32768
        or any(ord(char) < 33 or ord(char) > 126 for char in token)
        or value.get("token_type") != "Bearer"
        or not isinstance(scope, str)
        or len(scope) > 1024
        or not set(scope.split()).issubset(allowed_scopes)
        or not {WORK_IQ_SCOPE, "WorkIQAgent.Ask"}.intersection(scope.split())
    ):
        return {"error": "unknown"}
    result: dict[str, Any] = {
        "access_token": token,
        "token_type": "Bearer",
        "scope": scope,
    }
    for key in ("expires_in", "ext_expires_in"):
        if key in value:
            duration = value[key]
            if type(duration) is not int or not 1 <= duration <= 86400:
                return {"error": "unknown"}
            result[key] = duration
    return result


class BoundedOboHttp:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        loop: asyncio.AbstractEventLoop,
        tenant_id: str,
        deadline: float,
    ) -> None:
        tenant = str(UUID(tenant_id))
        authority = f"https://login.microsoftonline.com/{tenant}"
        self._metadata_url = f"{authority}/v2.0/.well-known/openid-configuration"
        self._metadata = {
            "token_endpoint": f"{authority}/oauth2/v2.0/token",
            "authorization_endpoint": f"{authority}/oauth2/v2.0/authorize",
            "issuer": f"{authority}/v2.0",
        }
        self._http = http
        self._loop = loop
        self._deadline = deadline
        self._lock = threading.Lock()
        self._closed = False
        self._pending: set[concurrent.futures.Future[_SafeResponse]] = set()
        self._tasks: set[asyncio.Task[Any]] = set()

    def get(self, url: str, **kwargs: Any) -> _SafeResponse:
        return self._submit("GET", url, kwargs)

    def post(self, url: str, **kwargs: Any) -> _SafeResponse:
        return self._submit("POST", url, kwargs)

    def _submit(self, method: str, url: str, kwargs: dict[str, Any]) -> _SafeResponse:
        allowed = (
            self._metadata_url if method == "GET" else self._metadata["token_endpoint"]
        )
        if url != allowed:
            raise WorkIQAuthenticationError("Work IQ identity endpoint is invalid")
        with self._lock:
            if self._closed or time.monotonic() >= self._deadline:
                raise WorkIQAuthenticationError("Work IQ identity exchange expired")
            pending = asyncio.run_coroutine_threadsafe(
                self._request(method, url, kwargs), self._loop
            )
            self._pending.add(pending)
        try:
            return pending.result(timeout=max(0, self._deadline - time.monotonic()))
        except (concurrent.futures.CancelledError, TimeoutError):
            pending.cancel()
            raise WorkIQAuthenticationError(
                "Work IQ identity exchange expired"
            ) from None
        finally:
            with self._lock:
                self._pending.discard(pending)

    async def _request(
        self, method: str, url: str, kwargs: dict[str, Any]
    ) -> _SafeResponse:
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        try:
            with suppress_instrumentation():
                async with asyncio.timeout(max(0, self._deadline - time.monotonic())):
                    async with self._http.stream(
                        method,
                        url,
                        headers=kwargs.get("headers"),
                        data=kwargs.get("data"),
                        params=kwargs.get("params"),
                        follow_redirects=False,
                        auth=None,
                        timeout=max(0.001, self._deadline - time.monotonic()),
                    ) as response:
                        allowed = (200,) if method == "GET" else (200, 400, 401)
                        if response.status_code not in allowed:
                            raise WorkIQAuthenticationError(
                                "Work IQ identity HTTP request failed"
                            )
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise WorkIQAuthenticationError(
                                    "Work IQ identity response exceeds size limit"
                                )
                            body.extend(chunk)
                        value = bounded_json(bytes(body))
                        if not isinstance(value, dict):
                            raise WorkIQAuthenticationError(
                                "Work IQ identity response is malformed"
                            )
                        if method == "GET":
                            if any(
                                value.get(key) != expected
                                for key, expected in self._metadata.items()
                            ):
                                raise WorkIQAuthenticationError(
                                    "Work IQ identity metadata is invalid"
                                )
                            return _SafeResponse(200, dict(self._metadata))
                        sanitized = _token_result(value)
                        if response.status_code != 200 and "error" not in sanitized:
                            sanitized = {"error": "unknown"}
                        return _SafeResponse(response.status_code, sanitized)
        except (httpx.HTTPError, TimeoutError, WorkIQProtocolError):
            raise WorkIQAuthenticationError(
                "Work IQ identity request unavailable"
            ) from None
        finally:
            self._tasks.discard(task)

    def cancel(self) -> None:
        """Wake synchronous waits and prevent the worker from starting more I/O."""
        with self._lock:
            self._closed = True
            pending = tuple(self._pending)
        for future in pending:
            future.cancel()

    async def aclose(self) -> None:
        self.cancel()
        # Cancellation acknowledgement (including response closure) precedes client closure.
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        await self._http.aclose()
