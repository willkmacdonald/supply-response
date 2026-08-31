from __future__ import annotations

from typing import Any, Final, NoReturn, Protocol, SupportsIndex

from apps.api.app.auth import UserAssertion

WORK_IQ_SCOPE: Final = "api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask"


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
    def __init__(self, confidential_client: ConfidentialClient) -> None:
        self._client = confidential_client

    def exchange(self, assertion: UserAssertion) -> WorkIQAccessToken:
        if not isinstance(assertion, UserAssertion):
            raise WorkIQAuthenticationError(
                "Work IQ requires a validated delegated user assertion"
            )
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
            or "WorkIQAgent.Ask" not in scopes.split()
        ):
            error = result.get("error")
            safe_code = (
                error[:64]
                if isinstance(error, str) and error.replace("_", "").isalnum()
                else "invalid_response"
            )
            raise WorkIQAuthenticationError(
                f"Work IQ delegated token exchange failed ({safe_code})"
            )
        return WorkIQAccessToken(token)


def build_obo_exchange(
    *, client_id: str, client_secret: str, tenant_id: str
) -> WorkIQOboExchange:
    """Build the production MSAL seam without exposing credentials elsewhere."""
    import msal

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    client = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )
    return WorkIQOboExchange(client)
