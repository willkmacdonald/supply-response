"""Opaque delegated Microsoft Graph token exchange."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final, NoReturn, Protocol, SupportsIndex
from uuid import UUID

from apps.api.app.auth import AuthenticatedActor, AuthorizationError, AuthService

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


def _validated_scopes(scope: object) -> frozenset[str] | None:
    values = scope.split() if isinstance(scope, str) else []
    if not values or any(value not in _SCOPE_ALIASES for value in values):
        return None
    normalized = frozenset(_SCOPE_ALIASES[value] for value in values)
    return normalized if _REQUIRED_SCOPES.issubset(normalized) else None


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
) -> GraphOboExchange:
    """Build a lazy production MSAL client using its supported HTTP path."""
    validated_client_id = str(UUID(client_id))
    validated_tenant_id = str(UUID(tenant_id))

    class LazyMsalClient:
        __slots__ = ("_client",)

        def __init__(self) -> None:
            self._client: Any = None

        def acquire_token_on_behalf_of(
            self, *, user_assertion: str, scopes: list[str]
        ) -> dict[str, Any]:
            if self._client is None:
                import msal

                self._client = msal.ConfidentialClientApplication(
                    client_id=validated_client_id,
                    client_credential=client_secret,
                    authority=(
                        f"https://login.microsoftonline.com/{validated_tenant_id}"
                    ),
                    instance_discovery=False,
                    timeout=GRAPH_OBO_TIMEOUT_SECONDS,
                )
            return self._client.acquire_token_on_behalf_of(
                user_assertion=user_assertion,
                scopes=scopes,
            )

    return GraphOboExchange(LazyMsalClient(), auth_service=auth_service)
