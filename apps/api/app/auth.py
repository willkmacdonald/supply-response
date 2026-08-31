from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, Final
from urllib.request import Request, urlopen
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource

_ALGORITHM: Final = "RS256"
_MAX_TOKEN_BYTES: Final = 32_768
_MAX_DOCUMENT_BYTES: Final = 256_000
_MAX_SIGNING_KEYS: Final = 16
_KNOWN_ROLES: Final = frozenset(
    {
        "material_planner",
        "response_approver",
        "quality_approver",
        "finance_approver",
    }
)


class AuthenticationError(ValueError):
    """The presented bearer token cannot be trusted."""


class AuthorizationError(PermissionError):
    """The trusted principal has no unambiguous demo-persona authorization."""


def _uuid(value: str, label: str) -> str:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a UUID") from error
    return str(parsed)


class PersonaBinding:
    __slots__ = (
        "tenant_id",
        "object_id",
        "persona_id",
        "allowed_roles",
        "source_id",
    )

    def __init__(
        self,
        *,
        tenant_id: str,
        object_id: str,
        persona_id: str,
        allowed_roles: Sequence[str],
        source_id: str,
    ) -> None:
        self.tenant_id = _uuid(tenant_id, "binding tenant ID")
        self.object_id = _uuid(object_id, "binding object ID")
        self.persona_id = persona_id.strip()
        self.allowed_roles = tuple(allowed_roles)
        self.source_id = source_id.strip()
        if not self.persona_id or not self.source_id:
            raise ValueError("binding persona and source IDs must be nonblank")
        if (
            not self.allowed_roles
            or len(self.allowed_roles) != len(set(self.allowed_roles))
            or not set(self.allowed_roles).issubset(_KNOWN_ROLES)
        ):
            raise ValueError("binding roles must be unique configured app roles")

    @classmethod
    def alex(cls, tenant_id: str, object_id: str) -> PersonaBinding:
        return cls(
            tenant_id=tenant_id,
            object_id=object_id,
            persona_id="RL-PERSONA-ALEX",
            allowed_roles=("material_planner", "response_approver"),
            source_id="RL-ENTRA-ALEX",
        )


class UserAssertion:
    """Opaque bearer assertion for downstream OBO; never serializes or displays."""

    __slots__ = ("__token",)

    def __init__(self, token: str) -> None:
        self.__token = token

    def reveal(self) -> str:
        """Return the assertion only at the downstream OBO call boundary."""
        return self.__token

    def __repr__(self) -> str:
        return "UserAssertion(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


class AuthenticatedActor:
    __slots__ = (
        "tenant_id",
        "object_id",
        "persona_id",
        "effective_roles",
        "display_name",
        "user_principal_name",
        "source_id",
        "downstream_user_assertion",
    )

    def __init__(
        self,
        *,
        tenant_id: str,
        object_id: str,
        persona_id: str,
        effective_roles: Sequence[str],
        display_name: str | None,
        user_principal_name: str | None,
        source_id: str,
        bearer_assertion: str,
    ) -> None:
        self.tenant_id = tenant_id
        self.object_id = object_id
        self.persona_id = persona_id
        self.effective_roles = tuple(sorted(effective_roles))
        self.display_name = display_name
        self.user_principal_name = user_principal_name
        self.source_id = source_id
        self.downstream_user_assertion = UserAssertion(bearer_assertion)

    def to_identity_snapshot(self) -> IdentitySnapshot:
        return IdentitySnapshot(
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            persona_id=self.persona_id,
            effective_roles=self.effective_roles,
            identity_source=IdentitySource.ENTRA,
            source_id=self.source_id,
            display_name=self.display_name,
            user_principal_name=self.user_principal_name,
        )

    def __repr__(self) -> str:
        return (
            "AuthenticatedActor("
            f"tenant_id={self.tenant_id!r}, object_id={self.object_id!r}, "
            f"persona_id={self.persona_id!r}, effective_roles={self.effective_roles!r}, "
            "downstream_user_assertion=<redacted>)"
        )


JsonFetcher = Callable[[str], Mapping[str, Any]]


def _http_get_json(url: str) -> Mapping[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed Entra URLs only
        body = response.read(_MAX_DOCUMENT_BYTES + 1)
    if len(body) > _MAX_DOCUMENT_BYTES:
        raise AuthenticationError("identity metadata response is too large")
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuthenticationError("identity metadata response is malformed") from error
    if not isinstance(value, dict):
        raise AuthenticationError("identity metadata response is malformed")
    return value


class AuthService:
    def __init__(
        self,
        *,
        tenant_id: str,
        audience: str,
        bindings: Sequence[PersonaBinding],
        http_get: JsonFetcher = _http_get_json,
        now: Callable[[], float] = time.time,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._tenant_id = _uuid(tenant_id, "tenant ID")
        self._audience = _uuid(audience, "audience")
        if not 30 <= cache_ttl_seconds <= 3600:
            raise ValueError("cache TTL must be between 30 and 3600 seconds")
        if not bindings:
            raise ValueError("at least one persona binding is required")
        by_identity: dict[tuple[str, str], PersonaBinding] = {}
        persona_ids: set[str] = set()
        source_ids: set[str] = set()
        for binding in bindings:
            key = (binding.tenant_id, binding.object_id)
            if (
                binding.tenant_id != self._tenant_id
                or key in by_identity
                or binding.persona_id in persona_ids
                or binding.source_id in source_ids
            ):
                raise ValueError("persona binding configuration is ambiguous")
            by_identity[key] = binding
            persona_ids.add(binding.persona_id)
            source_ids.add(binding.source_id)
        self._bindings = MappingProxyType(by_identity)
        self._issuer = f"https://login.microsoftonline.com/{self._tenant_id}/v2.0"
        self._metadata_url = f"{self._issuer}/.well-known/openid-configuration"
        self._expected_jwks_url = (
            f"https://login.microsoftonline.com/{self._tenant_id}/discovery/v2.0/keys"
        )
        self._http_get = http_get
        self._now = now
        self._cache_ttl = cache_ttl_seconds
        self._keys: Mapping[str, Mapping[str, Any]] = MappingProxyType({})
        self._cache_expires_at = 0.0

    def authenticate(
        self,
        token: str,
        *,
        bearer_assertion: str | None = None,
    ) -> AuthenticatedActor:
        if not isinstance(token, str):
            raise AuthenticationError("bearer token is malformed")
        if len(token.encode("utf-8")) > _MAX_TOKEN_BYTES:
            raise AuthenticationError("bearer token is too large")
        if token.count(".") != 2:
            raise AuthenticationError("bearer token is malformed")
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as error:
            raise AuthenticationError("bearer token is malformed") from error
        if header.get("alg") != _ALGORITHM:
            raise AuthenticationError("bearer token uses an unsupported algorithm")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id.strip():
            raise AuthenticationError("bearer token has no key identifier")
        key = self._signing_key(key_id)
        try:
            claims = jwt.decode(
                token,
                jwt.PyJWK.from_dict(dict(key)).key,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["iss", "aud", "exp", "nbf", "tid", "oid", "roles"],
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                },
            )
        except (InvalidTokenError, ValueError, TypeError) as error:
            raise AuthenticationError("bearer token validation failed") from error
        return self._authorize(claims, bearer_assertion or token)

    def _authorize(
        self, claims: Mapping[str, Any], bearer_assertion: str
    ) -> AuthenticatedActor:
        now = self._now()
        exp = claims.get("exp")
        nbf = claims.get("nbf")
        if (
            not isinstance(exp, (int, float))
            or isinstance(exp, bool)
            or not isinstance(nbf, (int, float))
            or isinstance(nbf, bool)
            or exp <= now
            or nbf > now
        ):
            raise AuthenticationError("bearer token lifetime is invalid")
        tenant_id = claims.get("tid")
        object_id = claims.get("oid")
        if (
            not isinstance(tenant_id, str)
            or tenant_id != self._tenant_id
            or not isinstance(object_id, str)
        ):
            raise AuthenticationError("bearer token tenant or object ID is invalid")
        try:
            object_id = _uuid(object_id, "token object ID")
        except ValueError as error:
            raise AuthenticationError("bearer token object ID is invalid") from error
        identity_provider = claims.get("idp")
        home_identity_providers = {
            self._issuer,
            f"https://sts.windows.net/{self._tenant_id}/",
        }
        if (
            identity_provider is not None
            and identity_provider not in home_identity_providers
        ):
            raise AuthenticationError(
                "guest or cross-tenant identities are not allowed"
            )
        binding = self._bindings.get((tenant_id, object_id))
        if binding is None:
            raise AuthorizationError(
                "no exact persona binding for token tenant/object ID"
            )
        roles = claims.get("roles")
        if (
            not isinstance(roles, list)
            or not roles
            or not all(isinstance(role, str) for role in roles)
            or len(roles) != len(set(roles))
        ):
            raise AuthorizationError("token roles are missing or ambiguous")
        if not set(roles).issubset(binding.allowed_roles):
            raise AuthorizationError("token role is not configured for persona binding")
        display_name = self._optional_string(claims, "name")
        upn = self._optional_string(claims, "preferred_username")
        return AuthenticatedActor(
            tenant_id=tenant_id,
            object_id=object_id,
            persona_id=binding.persona_id,
            effective_roles=roles,
            display_name=display_name,
            user_principal_name=upn,
            source_id=binding.source_id,
            bearer_assertion=bearer_assertion,
        )

    @staticmethod
    def _optional_string(claims: Mapping[str, Any], name: str) -> str | None:
        value = claims.get(name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            raise AuthenticationError(f"bearer token {name} claim is malformed")
        return value

    def _signing_key(self, key_id: str) -> Mapping[str, Any]:
        if self._now() >= self._cache_expires_at:
            self._refresh_keys(refresh_metadata=True)
        key = self._keys.get(key_id)
        if key is not None:
            return key
        # One bounded refresh handles normal Entra signing-key rotation. A second
        # retry is intentionally forbidden to avoid attacker-driven fetch loops.
        self._refresh_keys(refresh_metadata=False)
        key = self._keys.get(key_id)
        if key is None:
            raise AuthenticationError("bearer token signing key was not found")
        return key

    def _refresh_keys(self, *, refresh_metadata: bool) -> None:
        if refresh_metadata:
            metadata = self._fetch(self._metadata_url)
            if (
                metadata.get("issuer") != self._issuer
                or metadata.get("jwks_uri") != self._expected_jwks_url
            ):
                raise AuthenticationError("identity metadata issuer is invalid")
        document = self._fetch(self._expected_jwks_url)
        raw_keys = document.get("keys")
        if (
            not isinstance(raw_keys, list)
            or not 1 <= len(raw_keys) <= _MAX_SIGNING_KEYS
        ):
            raise AuthenticationError("identity signing key set has invalid size")
        parsed: dict[str, Mapping[str, Any]] = {}
        for key in raw_keys:
            if not isinstance(key, dict):
                raise AuthenticationError("identity signing key is malformed")
            key_id = key.get("kid")
            if (
                not isinstance(key_id, str)
                or not key_id
                or key_id in parsed
                or key.get("kty") != "RSA"
                or key.get("use") not in (None, "sig")
                or key.get("alg") not in (None, _ALGORITHM)
            ):
                message = (
                    "duplicate identity signing key"
                    if key_id in parsed
                    else "identity signing key is malformed"
                )
                raise AuthenticationError(message)
            parsed[key_id] = MappingProxyType(dict(key))
        self._keys = MappingProxyType(parsed)
        self._cache_expires_at = self._now() + self._cache_ttl

    def _fetch(self, url: str) -> Mapping[str, Any]:
        try:
            value = self._http_get(url)
        except AuthenticationError:
            raise
        except Exception as error:
            raise AuthenticationError("identity metadata fetch failed") from error
        if not isinstance(value, Mapping):
            raise AuthenticationError("identity metadata response is malformed")
        return value
