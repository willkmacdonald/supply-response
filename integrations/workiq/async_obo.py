"""A per-exchange MSAL worker with a joined lifetime and a 12-second I/O budget."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final
from uuid import UUID

import httpx
from opentelemetry.instrumentation.utils import suppress_instrumentation

from apps.api.app.auth import AuthenticatedActor, AuthService

from .obo import WorkIQAccessToken, WorkIQAuthenticationError, build_obo_exchange
from .obo_http import BoundedOboHttp

OBO_TIMEOUT_SECONDS: Final = 12


async def _finish_cleanup(task: asyncio.Task[None]) -> None:
    """Repeated caller cancellation cannot detach credential-bearing work."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


class AsyncWorkIQOboExchange:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        auth_service: AuthService,
    ) -> None:
        self._client_id = str(UUID(client_id))
        self._tenant_id = str(UUID(tenant_id))
        self._client_secret = client_secret
        if not isinstance(auth_service, AuthService):
            raise TypeError("Work IQ OBO requires an AuthService instance")
        self._auth_service = auth_service

    async def exchange(self, actor: AuthenticatedActor) -> WorkIQAccessToken:
        loop = asyncio.get_running_loop()
        deadline = time.monotonic() + OBO_TIMEOUT_SECONDS
        http = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
        )
        adapter = BoundedOboHttp(
            http=http, loop=loop, tenant_id=self._tenant_id, deadline=deadline
        )
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="workiq-obo")

        def acquire() -> WorkIQAccessToken:
            # Construction is lazy: the real AuthService validates the actor before MSAL discovery.
            exchange: Any = None
            try:
                with suppress_instrumentation():
                    exchange = build_obo_exchange(
                        client_id=self._client_id,
                        client_secret=self._client_secret,
                        tenant_id=self._tenant_id,
                        auth_service=self._auth_service,
                        http_client=adapter,
                    )
                    return exchange.exchange(actor)
            except Exception:  # noqa: BLE001, S110 - sanitized error raised outside handler
                pass
            finally:
                exchange = None
            # Raising outside the handler removes even the hidden exception context.
            raise WorkIQAuthenticationError("Work IQ delegated token exchange failed")

        worker = loop.run_in_executor(executor, acquire)

        async def cleanup() -> None:
            adapter.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            executor.shutdown(wait=True, cancel_futures=True)
            await adapter.aclose()

        try:
            async with asyncio.timeout(max(0, deadline - time.monotonic())):
                return await asyncio.shield(worker)
        except TimeoutError:
            raise WorkIQAuthenticationError(
                "Work IQ delegated token exchange timed out"
            ) from None
        finally:
            await _finish_cleanup(asyncio.create_task(cleanup()))
