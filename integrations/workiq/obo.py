from __future__ import annotations

import logging
from typing import Any, Final, NoReturn, Protocol, SupportsIndex

from apps.api.app.auth import AuthenticatedActor, AuthorizationError, AuthService

WORK_IQ_SCOPE: Final = "api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask"
_logger = logging.getLogger(__name__)
# Only these known protocol codes may leave the token-response boundary.
# Unknown values are not echoed, even if they look like harmless identifiers.
_OAUTH_ERRORS: Final = frozenset(
    {
        "invalid_request",
        "invalid_client",
        "invalid_grant",
        "invalid_scope",
        "unauthorized_client",
        "unsupported_grant_type",
        "interaction_required",
        "consent_required",
        "access_denied",
        "temporarily_unavailable",
        "server_error",
    }
)
_AAD_CODES: Final = frozenset(
    {
        500011,
        500131,
        50076,
        50079,
        53003,
        65001,
        65004,
        650057,
        70000,
        70011,
        700016,
        7000215,
        7000222,
    }
)


def _log_rejected_response(result: dict[str, Any]) -> str:
    """Log only allowlisted codes and booleans, never raw response values."""
    error = result.get("error")
    safe_code = (
        error if isinstance(error, str) and error in _OAUTH_ERRORS else "unknown"
    )
    codes = result.get("error_codes")
    first_code = codes[0] if isinstance(codes, list) and codes else None
    aad_code = (
        first_code
        if type(first_code) is int and first_code in _AAD_CODES
        else "unknown"
    )
    token = result.get("access_token")
    scopes = result.get("scope")
    scope_values = scopes.split() if isinstance(scopes, str) else []
    _logger.warning(
        "workiq_obo_failed outcome=%s oauth_error=%s aad_code=%s "
        "token_present=%s bearer_type=%s scope_unqualified=%s scope_qualified=%s",
        "remote_error" if isinstance(error, str) and error else "response_rejected",
        safe_code,
        aad_code,
        isinstance(token, str) and bool(token.strip()),
        result.get("token_type") == "Bearer",
        "WorkIQAgent.Ask" in scope_values,
        WORK_IQ_SCOPE in scope_values,
    )
    return safe_code


class WorkIQAuthenticationError(PermissionError):
    """A delegated Work IQ token could not be obtained safely."""


class ConfidentialClient(Protocol):
    def acquire_token_on_behalf_of(
        self, *, user_assertion: str, scopes: list[str]
    ) -> dict[str, Any]: ...


class WorkIQAccessToken:
    """Opaque downstream token that cannot be printed accidentally."""

    __slots__ = ("__token",)

    def __init__(self, token: str) -> None:
        self.__token = token

    def reveal(self) -> str:
        return self.__token

    def __repr__(self) -> str:
        return "WorkIQAccessToken(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("WorkIQAccessToken cannot be serialized")


class WorkIQOboExchange:
    def __init__(
        self, confidential_client: ConfidentialClient, *, auth_service: AuthService
    ) -> None:
        self._client = confidential_client
        if not isinstance(auth_service, AuthService):
            raise TypeError("Work IQ OBO requires an AuthService instance")
        self._auth_service = auth_service

    def exchange(self, actor: AuthenticatedActor) -> WorkIQAccessToken:
        if (
            not isinstance(actor, AuthenticatedActor)
            or actor.persona_id != "RL-PERSONA-ALEX"
            or actor.source_id != "RL-ENTRA-ALEX"
            or actor.effective_roles != ("material_planner", "response_approver")
            or actor.delegated_scopes != ("access_as_user",)
        ):
            raise WorkIQAuthenticationError(
                "Work IQ requires the validated delegated Alex actor"
            )
        try:
            assertion = self._auth_service._validated_user_assertion(actor)
        except AuthorizationError as error:
            raise WorkIQAuthenticationError(
                "Work IQ requires an actor from the configured AuthService"
            ) from error
        result = self._client.acquire_token_on_behalf_of(
            user_assertion=assertion.reveal(),
            scopes=[WORK_IQ_SCOPE],
        )
        if not isinstance(result, dict):
            raise WorkIQAuthenticationError("Work IQ token exchange failed")
        token = result.get("access_token")
        token_type = result.get("token_type")
        scopes = result.get("scope")
        if (
            not isinstance(token, str)
            or not token.strip()
            or token_type != "Bearer"
            or not isinstance(scopes, str)
            # Entra may return the resource-qualified form requested above.
            # Match complete tokens only, never suffixes or other resources.
            or not {"WorkIQAgent.Ask", WORK_IQ_SCOPE}.intersection(scopes.split())
        ):
            safe_code = _log_rejected_response(result)
            raise WorkIQAuthenticationError(
                f"Work IQ delegated token exchange failed ({safe_code})"
            )
        return WorkIQAccessToken(token)


def build_obo_exchange(
    *,
    client_id: str,
    client_secret: str,
    tenant_id: str,
    auth_service: AuthService,
) -> WorkIQOboExchange:
    """Build a lazy production MSAL seam; construction performs no discovery."""

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
                    client_id=client_id,
                    client_credential=client_secret,
                    authority=f"https://login.microsoftonline.com/{tenant_id}",
                    instance_discovery=False,
                )
            return self._client.acquire_token_on_behalf_of(
                user_assertion=user_assertion, scopes=scopes
            )

    client = LazyMsalClient()
    return WorkIQOboExchange(client, auth_service=auth_service)
