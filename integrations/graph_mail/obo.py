"""Opaque delegated Microsoft Graph token exchange."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final, NoReturn, Protocol, SupportsIndex
from uuid import UUID

import httpx
from opentelemetry.instrumentation.utils import suppress_instrumentation

from apps.api.app.auth import AuthenticatedActor, AuthorizationError, AuthService
from integrations.workiq.mcp import MAX_RESPONSE_BYTES, bounded_json

GRAPH_SCOPES: Final = (
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
)
GRAPH_DEFAULT_SCOPE: Final = "https://graph.microsoft.com/.default"
GRAPH_OBO_TIMEOUT_SECONDS: Final = 12
_MAX_TOKEN_BYTES: Final = 32_768
_REQUIRED_SCOPES: Final = frozenset({"Mail.ReadWrite", "Mail.Send"})
_SCOPE_ALIASES: Final = {
    "Mail.ReadWrite": "Mail.ReadWrite",
    GRAPH_SCOPES[0]: "Mail.ReadWrite",
    "Mail.Send": "Mail.Send",
    GRAPH_SCOPES[1]: "Mail.Send",
    "openid": "openid",
    "profile": "profile",
    "offline_access": "offline_access",
}
_OAUTH_ERRORS: Final = frozenset(
    {
        "invalid_request",
        "invalid_client",
        "invalid_grant",
        "invalid_scope",
        "unauthorized_client",
        "interaction_required",
        "consent_required",
        "access_denied",
        "temporarily_unavailable",
        "server_error",
    }
)
_logger = logging.getLogger(__name__)


def _safe_aad_code(value: object) -> int | str:
    # Entra error codes are bounded integers. Unlike provider text, they cannot
    # carry tokens, identifiers, claims, or free-form message content.
    return value if type(value) is int and 10_000 <= value <= 99_999_999 else "unknown"


def _log_rejected_response(result: dict[str, Any]) -> str:
    """Log only allowlisted categories; never provider text or credentials."""
    error = result.get("error")
    safe_code = (
        error if isinstance(error, str) and error in _OAUTH_ERRORS else "unknown"
    )
    codes = result.get("error_codes")
    first_code = codes[0] if isinstance(codes, list) and codes else None
    aad_code = _safe_aad_code(first_code)
    token = result.get("access_token")
    scopes = result.get("scope")
    scope_values = scopes.split() if isinstance(scopes, str) else []
    _logger.warning(
        "graph_obo_failed outcome=%s oauth_error=%s aad_code=%s "
        "token_present=%s bearer_type=%s mail_readwrite=%s mail_send=%s",
        "remote_error" if isinstance(error, str) and error else "response_rejected",
        safe_code,
        aad_code,
        isinstance(token, str) and bool(token.strip()),
        result.get("token_type") == "Bearer",
        any(value in {"Mail.ReadWrite", GRAPH_SCOPES[0]} for value in scope_values),
        any(value in {"Mail.Send", GRAPH_SCOPES[1]} for value in scope_values),
    )
    return safe_code


class GraphAuthenticationError(PermissionError):
    """A delegated Graph token could not be obtained safely."""


class ConfidentialClient(Protocol):
    def acquire_token_on_behalf_of(
        self, *, user_assertion: str, scopes: list[str]
    ) -> dict[str, Any]: ...


class GraphAccessToken:
    """Opaque downstream token that cannot be printed or serialized."""

    __slots__ = ("__token",)

    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Graph access token is empty")
        self.__token = token

    def reveal(self) -> str:
        return self.__token

    def __repr__(self) -> str:
        return "GraphAccessToken(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("GraphAccessToken cannot be serialized")


class _SafeResponse:
    def __init__(self, status: int, value: dict[str, Any]) -> None:
        self.status_code = status
        self.text = json.dumps(value)
        self.headers: dict[str, str] = {}

    def __repr__(self) -> str:
        return "GraphOboResponse(<redacted>)"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise GraphAuthenticationError("Graph identity request failed")


def _validated_scopes(scope: object) -> frozenset[str] | None:
    values = scope.split() if isinstance(scope, str) else []
    if not values or any(value not in _SCOPE_ALIASES for value in values):
        return None
    normalized = frozenset(_SCOPE_ALIASES[value] for value in values)
    return normalized if _REQUIRED_SCOPES.issubset(normalized) else None


def _safe_token_result(value: dict[str, Any]) -> dict[str, Any]:
    if "error" in value:
        code = value.get("error")
        codes = value.get("error_codes")
        return {
            "error": code if code in _OAUTH_ERRORS else "unknown",
            "error_codes": [
                candidate
                for candidate in codes
                if _safe_aad_code(candidate) != "unknown"
            ][:1]
            if isinstance(codes, list)
            else [],
        }
    token = value.get("access_token")
    scope = value.get("scope")
    scopes = _validated_scopes(scope)
    if (
        not isinstance(token, str)
        or not 1 <= len(token.encode("utf-8")) <= _MAX_TOKEN_BYTES
        or any(ord(character) < 33 or ord(character) > 126 for character in token)
        or value.get("token_type") != "Bearer"
        or scopes is None
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
            if type(duration) is not int or not 1 <= duration <= 86_400:
                return {"error": "unknown"}
            result[key] = duration
    return result


class _BoundedGraphOboHttp:
    """MSAL's sync HTTP seam backed by bounded async I/O."""

    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        loop: asyncio.AbstractEventLoop,
        tenant_id: str,
        deadline: float,
    ) -> None:
        authority = f"https://login.microsoftonline.com/{UUID(tenant_id)}"
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
            raise GraphAuthenticationError("Graph identity endpoint is invalid")
        with self._lock:
            if self._closed or time.monotonic() >= self._deadline:
                raise GraphAuthenticationError("Graph identity exchange expired")
            pending = asyncio.run_coroutine_threadsafe(
                self._request(method, url, kwargs), self._loop
            )
            self._pending.add(pending)
        try:
            return pending.result(timeout=max(0, self._deadline - time.monotonic()))
        except (concurrent.futures.CancelledError, TimeoutError):
            pending.cancel()
            raise GraphAuthenticationError("Graph identity exchange expired") from None
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
                            raise GraphAuthenticationError(
                                "Graph identity HTTP request failed"
                            )
                        if not _json_media_type(
                            response.headers.get("content-type", "")
                        ):
                            raise GraphAuthenticationError(
                                "Graph identity response is malformed"
                            )
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise GraphAuthenticationError(
                                    "Graph identity response exceeds size limit"
                                )
                            body.extend(chunk)
                        try:
                            value = bounded_json(bytes(body))
                        except Exception:  # noqa: BLE001 - convert Work IQ parser errors
                            raise GraphAuthenticationError(
                                "Graph identity response is malformed"
                            ) from None
                        if not isinstance(value, dict):
                            raise GraphAuthenticationError(
                                "Graph identity response is malformed"
                            )
                        if method == "GET":
                            if any(
                                value.get(key) != expected
                                for key, expected in self._metadata.items()
                            ):
                                raise GraphAuthenticationError(
                                    "Graph identity metadata is invalid"
                                )
                            return _SafeResponse(200, dict(self._metadata))
                        sanitized = _safe_token_result(value)
                        if response.status_code != 200 and "error" not in sanitized:
                            sanitized = {"error": "unknown"}
                        return _SafeResponse(response.status_code, sanitized)
        except (httpx.HTTPError, TimeoutError):
            raise GraphAuthenticationError(
                "Graph identity request unavailable"
            ) from None
        finally:
            self._tasks.discard(task)

    def cancel(self) -> None:
        with self._lock:
            self._closed = True
            pending = tuple(self._pending)
        for future in pending:
            future.cancel()

    async def aclose(self) -> None:
        self.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        await self._http.aclose()


def _json_media_type(value: str) -> bool:
    media_type = value.partition(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


class GraphOboExchange:
    def __init__(
        self, confidential_client: ConfidentialClient, *, auth_service: AuthService
    ) -> None:
        self._client = confidential_client
        if not isinstance(auth_service, AuthService):
            raise TypeError("Graph OBO requires an AuthService instance")
        self._auth_service = auth_service

    def _exchange_sync(self, actor: object) -> GraphAccessToken:
        if (
            not isinstance(actor, AuthenticatedActor)
            or actor.persona_id != "RL-PERSONA-ALEX"
            or actor.source_id != "RL-ENTRA-ALEX"
            or actor.effective_roles != ("material_planner", "response_approver")
            or actor.delegated_scopes != ("access_as_user",)
        ):
            raise GraphAuthenticationError(
                "Graph mail requires the validated delegated Alex actor"
            )
        try:
            assertion = self._auth_service._validated_user_assertion(actor)
        except AuthorizationError:
            raise GraphAuthenticationError(
                "Graph mail requires an actor from the configured AuthService"
            ) from None
        try:
            result = self._client.acquire_token_on_behalf_of(
                user_assertion=assertion.reveal(), scopes=[GRAPH_DEFAULT_SCOPE]
            )
        except Exception:  # noqa: BLE001 - sanitize provider/library details
            raise GraphAuthenticationError(
                "Graph delegated token exchange failed"
            ) from None
        if not isinstance(result, dict):
            raise GraphAuthenticationError("Graph delegated token exchange failed")
        token = result.get("access_token")
        token_type = result.get("token_type")
        granted = _validated_scopes(result.get("scope"))
        if (
            not isinstance(token, str)
            or not token.strip()
            or len(token.encode("utf-8")) > _MAX_TOKEN_BYTES
            or token_type != "Bearer"
            or granted is None
        ):
            _log_rejected_response(result)
            raise GraphAuthenticationError("Graph delegated token exchange failed")
        return GraphAccessToken(token)

    async def exchange(self, actor: object) -> GraphAccessToken:
        try:
            async with asyncio.timeout(GRAPH_OBO_TIMEOUT_SECONDS):
                return await asyncio.to_thread(self._exchange_sync, actor)
        except TimeoutError:
            raise GraphAuthenticationError(
                "Graph delegated token exchange timed out"
            ) from None


def build_graph_obo_exchange(
    *,
    client_id: str,
    client_secret: str,
    tenant_id: str,
    auth_service: AuthService,
) -> AsyncGraphOboExchange:
    return AsyncGraphOboExchange(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        auth_service=auth_service,
    )


class AsyncGraphOboExchange:
    """Run MSAL OBO with a joined worker and bounded, redirect-free HTTP."""

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
            raise TypeError("Graph OBO requires an AuthService instance")
        self._auth_service = auth_service

    async def exchange(self, actor: object) -> GraphAccessToken:
        loop = asyncio.get_running_loop()
        deadline = time.monotonic() + GRAPH_OBO_TIMEOUT_SECONDS
        http = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
        )
        adapter = _BoundedGraphOboHttp(
            http=http,
            loop=loop,
            tenant_id=self._tenant_id,
            deadline=deadline,
        )
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="graph-obo")

        def acquire() -> GraphAccessToken:
            try:
                with suppress_instrumentation():
                    exchange = _build_msal_exchange(
                        client_id=self._client_id,
                        client_secret=self._client_secret,
                        tenant_id=self._tenant_id,
                        auth_service=self._auth_service,
                        http_client=adapter,
                    )
                    return exchange._exchange_sync(actor)
            except Exception:  # noqa: BLE001 - sanitize all credential-bound errors
                raise GraphAuthenticationError(
                    "Graph delegated token exchange failed"
                ) from None

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
            raise GraphAuthenticationError(
                "Graph delegated token exchange timed out"
            ) from None
        finally:
            cleanup_task = asyncio.create_task(cleanup())
            cancelled = False
            while not cleanup_task.done():
                try:
                    await asyncio.shield(cleanup_task)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup_task.result()
            if cancelled:
                raise asyncio.CancelledError


def _build_msal_exchange(
    *,
    client_id: str,
    client_secret: str,
    tenant_id: str,
    auth_service: AuthService,
    http_client: Any,
) -> GraphOboExchange:
    import msal

    confidential = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        instance_discovery=False,
        http_client=http_client,
    )
    return GraphOboExchange(confidential, auth_service=auth_service)
