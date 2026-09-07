"""Temporary MSAL adapter: bounded async I/O behind its synchronous interface."""

import asyncio
import json
import time
from typing import Any

import httpx

from .obo import WORK_IQ_SCOPE


class DiagnosticMsalHttp:
    def __init__(
        self, *, transport: httpx.AsyncBaseTransport | None = None, budget: float = 12
    ) -> None:
        self._transport = transport
        self._budget = budget
        self._deadline: float | None = None

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._deadline is None:
            self._deadline = time.monotonic() + self._budget
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("diagnostic identity timeout")
        kwargs.pop("timeout", None)
        return asyncio.run(self._send(method, url, remaining, kwargs))

    async def _send(
        self, method: str, url: str, remaining: float, kwargs: dict[str, Any]
    ) -> httpx.Response:
        async with asyncio.timeout(remaining):
            async with httpx.AsyncClient(
                transport=self._transport, follow_redirects=False, timeout=remaining
            ) as client:
                async with client.stream(method, url, **kwargs) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 1024 * 1024:
                            raise ValueError("diagnostic identity response too large")
                    if response.status_code != 200:
                        raise ValueError("diagnostic identity request failed")
                    # Never let MSAL see malformed bytes: oauth2cli logs them.
                    try:
                        value = json.loads(body)
                        if not isinstance(value, dict):
                            raise TypeError
                    except (ValueError, UnicodeError, TypeError):
                        raise ValueError(
                            "diagnostic identity response invalid"
                        ) from None
                    # OBO does not need ID/refresh tokens or arbitrary provider errors.
                    if method == "POST":
                        token, scopes = value.get("access_token"), value.get("scope")
                        if (
                            not isinstance(token, str)
                            or not token.strip()
                            or value.get("token_type") != "Bearer"
                            or not isinstance(scopes, str)
                            or not {"WorkIQAgent.Ask", WORK_IQ_SCOPE}.intersection(
                                scopes.split()
                            )
                        ):
                            raise ValueError("diagnostic identity token invalid")
                        value = {
                            "access_token": token,
                            "token_type": "Bearer",
                            "scope": WORK_IQ_SCOPE,
                        }
                    return httpx.Response(200, json=value)
