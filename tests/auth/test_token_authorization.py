from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from apps.api.app.auth import (
    AuthenticationError,
    AuthorizationError,
    AuthService,
    PersonaBinding,
)

TENANT_ID = "11111111-1111-4111-8111-111111111111"
API_CLIENT_ID = "22222222-2222-4222-8222-222222222222"
ALEX_OID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
JORDAN_OID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
METADATA_URL = f"{ISSUER}/.well-known/openid-configuration"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
NOW = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)

PRIVATE_KEY = b"""-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDRGbHwX0TTqxgn
kBD1RrvoSi3lBDyrF8u3dOVdlpqDpMfFl1ooyJ02JT35AQFRiXkVUg+1yNETHQrx
EGfFMnxHqQmrjp+4o2INVhsBMILEH64FsPa2gqT8ADlDM5YpRs3fZkLJY1IhUvxm
hLEvkzZVIHP6+7sssVwPqq4FCEX6FBO/UXyQ4+osTQjskLQlzrMCfCKZauH7ZKxz
TkA1mcvHH9WAfRNtPvA1t5ICHNm6DjA6IrqpBbhAZSegR9/oVaWTNQcqZMO9hjIQ
xBNYY0JPY0MAVddTvYOkEtpngfNpiO4PdN1u+AX+kUmVCpAJntfLevQ0pcg79hqq
7ifaZIOxAgMBAAECggEABoOavoFJSfV85Xv10J5T1khmpkl71lysalpdluJ34n1X
V+QqLou+vLlrn9Pp2u9scpSW4V6Qh4bnw1tz0CSNffIEghq0W8fYkyUekZVATaSA
WF8LSzjws4USQ5yveI5jICrgY8O7WEcXOTO4YrdfAZyRixJyjKbjK6hxOWjo59cl
MpiHYyw6+3CGWlx0XhxKu3pRX+iOKfbigrnFCwA4haCAYCM5gHW6IR1WRnTmQVUj
CeuBMwk/eXPTIOzH2jco+D+650LFk7t7BSeSjYavhf79vSFkSBw/P0KNzMvrglXC
II2kOGNWPhWyYEYLARkFqlHw+VsqITA16GE7PigGEQKBgQDoO0s7/gIQevXRE6Bg
rwxZ9O/HxG+xmIEMVC26PFcP6Lp/DByQGXwKlwHYVJyIo0vjJtRNZNeGWgGJtsRv
XjryJ4I7OtnZdxgBU/YLGmOQqOeMkJf4QR1nMOx2cep6cVLfeqKNHewZwtD6UlOJ
LEBwp9P7YD0DtdllGZ4B/SHgxQKBgQDmgFbA107rFFVdBK5yqAmWeuFNeH7g/hJA
f+QoQRMldt1Kq+6fXrmWD3Vk8QWDwh1pUoRphT4OHlD8kcuQw71DhgaUDkL2f/nn
Q6XRxQ2lx0UzxGdiwCM4zrU9zCpOGMdIGGHei12Yts5WSTlv4VYIGB/EYV6Xlz9j
R/Gcbrft/QKBgQCTNytNP4t9eQUlYeS0BaO1zvDF2X/YvE1qTF6khaXHPwgii8H7
kzwv1mRkB9cnQyVTPQUufrOlxp7c9xB1bO2/Hk6PT5JUKgv8o4YAqdzeEkSetfaw
eE60YK41s6cpsXcQlkQ/Yu2NsxMY7GFqPrQm9i0KWIq1NG04itHAfwAf5QKBgQCC
PD9IJB8F+e4laXC7fbA1IubL4+oka8maQeiCygnsYBW2jCB+UYIghEl7KCdKg9Ik
YShJiqw+Q+jUW/gdqkr0rPRokQpKxpJHldRKCsGkSkwSbMVRaWg9P6Xt7b51c9Cd
LpGVsT7H+3noDOV0DmiSmDbSuYU9t4psKQkdrv0jbQKBgQCLq5Xsnp6hCwt19exj
LGqXF4T/2+dYC1dlVlS8HTXyTECAQEwO5Xs32Nz1fRfpj4bWrZzQCC6eDvKz7LB1
Rpg0lBQYulNNeFjPAdVA4JlkGlx+yt879ZMsTs0qBsTBy3Ojlu75eMgK1F3p5S7Y
OxK7yePSBGQV5qNhajdYK8I52Q==
-----END PRIVATE KEY-----"""


def _jwk(key_id: str = "fixture-key") -> dict[str, Any]:
    private_key = serialization.load_pem_private_key(PRIVATE_KEY, password=None)
    assert isinstance(private_key, rsa.RSAPrivateKey)
    value = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    value.update({"kid": key_id, "use": "sig", "alg": "RS256"})
    return value


class FixtureHttp:
    def __init__(self) -> None:
        self.metadata = {"issuer": ISSUER, "jwks_uri": JWKS_URL}
        self.jwks = {"keys": [_jwk()]}
        self.calls: list[str] = []

    def __call__(self, url: str) -> dict[str, Any]:
        self.calls.append(url)
        if url == METADATA_URL:
            return self.metadata
        if url == JWKS_URL:
            return self.jwks
        raise AssertionError(f"unexpected URL: {url}")


@pytest.fixture
def fixture_http() -> FixtureHttp:
    return FixtureHttp()


@pytest.fixture
def auth_service(fixture_http: FixtureHttp) -> AuthService:
    return AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(
            PersonaBinding(
                tenant_id=TENANT_ID,
                object_id=ALEX_OID,
                persona_id="RL-PERSONA-ALEX",
                allowed_roles=("material_planner", "response_approver"),
                source_id="RL-ENTRA-ALEX",
            ),
            PersonaBinding(
                tenant_id=TENANT_ID,
                object_id=JORDAN_OID,
                persona_id="RL-PERSONA-JORDAN",
                allowed_roles=("quality_approver",),
                source_id="RL-ENTRA-JORDAN",
            ),
        ),
        http_get=fixture_http,
        now=lambda: NOW.timestamp(),
        cache_ttl_seconds=300,
    )


@pytest.fixture
def token_factory():
    def make(**overrides: Any) -> str:
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": API_CLIENT_ID,
            "iat": int(NOW.timestamp()) - 5,
            "nbf": int(NOW.timestamp()) - 5,
            "exp": int(NOW.timestamp()) + 300,
            "tid": TENANT_ID,
            "oid": ALEX_OID,
            "roles": ["material_planner", "response_approver"],
            "preferred_username": "alex@willmacdonald.com",
            "name": "Alex Morgan",
        }
        headers = overrides.pop("headers", {"kid": "fixture-key", "typ": "JWT"})
        claims.update(overrides)
        return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers=headers)

    return make


def test_alex_token_maps_stable_persona_and_roles(token_factory, auth_service):
    actor = auth_service.authenticate(
        token_factory(), bearer_assertion="original-token"
    )

    assert actor.persona_id == "RL-PERSONA-ALEX"
    assert actor.effective_roles == ("material_planner", "response_approver")
    assert actor.downstream_user_assertion.reveal() == "original-token"


@pytest.mark.parametrize(
    ("claim", "value"),
    [("tid", "33333333-3333-4333-8333-333333333333"), ("aud", "wrong-api")],
)
def test_wrong_tenant_or_audience_is_rejected(
    token_factory, auth_service, claim, value
):
    with pytest.raises(AuthenticationError):
        auth_service.authenticate(token_factory(**{claim: value}))


def test_upn_alone_never_authorizes(token_factory, auth_service):
    token = token_factory(
        oid="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        preferred_username="alex@willmacdonald.com",
    )
    with pytest.raises(AuthorizationError, match="persona binding"):
        auth_service.authenticate(token)


def test_home_tenant_sts_identity_provider_is_allowed(token_factory, auth_service):
    actor = auth_service.authenticate(
        token_factory(idp=f"https://sts.windows.net/{TENANT_ID}/")
    )
    assert actor.persona_id == "RL-PERSONA-ALEX"


@pytest.mark.parametrize(
    "mutation",
    [
        {"exp": int(NOW.timestamp()) - 1},
        {"nbf": int(NOW.timestamp()) + 60},
        {"oid": None},
        {"tid": None},
        {"iss": "https://login.microsoftonline.com/common/v2.0"},
        {"idp": "https://sts.windows.net/foreign-tenant/"},
        {"roles": "response_approver"},
        {"roles": ["response_approver", "response_approver"]},
        {"roles": ["response_approver", "unconfigured_role"]},
    ],
)
def test_malformed_or_untrusted_claims_are_rejected(
    token_factory, auth_service, mutation
):
    with pytest.raises((AuthenticationError, AuthorizationError)):
        auth_service.authenticate(token_factory(**mutation))


def test_algorithm_confusion_and_missing_kid_are_rejected(token_factory, auth_service):
    unsigned = jwt.encode(
        {"tid": TENANT_ID, "oid": ALEX_OID},
        key="",
        algorithm="none",
        headers={"typ": "JWT"},
    )
    with pytest.raises(AuthenticationError, match="algorithm"):
        auth_service.authenticate(unsigned)

    with pytest.raises(AuthenticationError, match="key identifier"):
        auth_service.authenticate(token_factory(headers={"typ": "JWT"}))


def test_metadata_and_jwks_are_cached_with_bounded_kid_refresh(
    token_factory, auth_service, fixture_http
):
    auth_service.authenticate(token_factory())
    auth_service.authenticate(token_factory())
    assert fixture_http.calls == [METADATA_URL, JWKS_URL]

    with pytest.raises(AuthenticationError, match="signing key"):
        auth_service.authenticate(
            token_factory(headers={"kid": "rotated-key", "typ": "JWT"})
        )
    assert fixture_http.calls == [METADATA_URL, JWKS_URL, JWKS_URL]


def test_kid_rotation_refreshes_once_and_accepts_the_new_key(
    token_factory, auth_service, fixture_http
):
    auth_service.authenticate(token_factory())
    fixture_http.jwks = {"keys": [_jwk("rotated-key")]}

    actor = auth_service.authenticate(
        token_factory(headers={"kid": "rotated-key", "typ": "JWT"})
    )

    assert actor.persona_id == "RL-PERSONA-ALEX"
    assert fixture_http.calls == [METADATA_URL, JWKS_URL, JWKS_URL]


def test_expired_cache_refreshes_metadata_and_keys(token_factory, fixture_http):
    clock = [NOW.timestamp()]
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OID),),
        http_get=fixture_http,
        now=lambda: clock[0],
        cache_ttl_seconds=300,
    )
    service.authenticate(token_factory(exp=int(NOW.timestamp()) + 1000))
    clock[0] += 301
    service.authenticate(token_factory(exp=int(NOW.timestamp()) + 1000))

    assert fixture_http.calls == [METADATA_URL, JWKS_URL, METADATA_URL, JWKS_URL]


def test_untrusted_metadata_and_bad_signature_are_rejected(token_factory, fixture_http):
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OID),),
        http_get=fixture_http,
        now=lambda: NOW.timestamp(),
    )
    fixture_http.metadata["issuer"] = "https://login.microsoftonline.com/common/v2.0"
    with pytest.raises(AuthenticationError, match="metadata issuer"):
        service.authenticate(token_factory())

    fixture_http.metadata["issuer"] = ISSUER
    token = token_factory()
    header, payload, signature = token.split(".")
    signature = f"{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
    tampered = ".".join((header, payload, signature))
    with pytest.raises(AuthenticationError, match="validation failed"):
        service.authenticate(tampered)


def test_duplicate_jwks_is_rejected(token_factory, fixture_http):
    fixture_http.jwks = {"keys": [_jwk(), _jwk()]}
    service = AuthService(
        tenant_id=TENANT_ID,
        audience=API_CLIENT_ID,
        bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OID),),
        http_get=fixture_http,
        now=lambda: NOW.timestamp(),
    )
    with pytest.raises(AuthenticationError, match="duplicate"):
        service.authenticate(token_factory())

    fixture_http.calls.clear()
    fixture_http.jwks = {"keys": [_jwk(f"key-{index}") for index in range(17)]}
    with pytest.raises(AuthenticationError, match="invalid size"):
        service.authenticate(token_factory())


@pytest.mark.parametrize(
    "bindings",
    [
        (),
        (PersonaBinding.alex(TENANT_ID, ALEX_OID),) * 2,
        (
            PersonaBinding.alex(TENANT_ID, ALEX_OID),
            PersonaBinding(
                tenant_id=TENANT_ID,
                object_id=JORDAN_OID,
                persona_id="RL-PERSONA-ALEX",
                allowed_roles=("quality_approver",),
                source_id="RL-ENTRA-JORDAN",
            ),
        ),
    ],
)
def test_missing_or_ambiguous_binding_configuration_is_rejected(bindings):
    with pytest.raises(ValueError, match="binding"):
        AuthService(tenant_id=TENANT_ID, audience=API_CLIENT_ID, bindings=bindings)


def test_non_uuid_api_audience_configuration_is_rejected():
    with pytest.raises(ValueError, match="audience"):
        AuthService(
            tenant_id=TENANT_ID,
            audience="api://not-an-api-client-id",
            bindings=(PersonaBinding.alex(TENANT_ID, ALEX_OID),),
        )


def test_actor_snapshot_includes_identity_but_never_bearer(token_factory, auth_service):
    bearer = token_factory()
    actor = auth_service.authenticate(bearer)
    snapshot = actor.to_identity_snapshot()
    encoded = snapshot.model_dump_json()

    assert snapshot.tenant_id == TENANT_ID
    assert snapshot.object_id == ALEX_OID
    assert snapshot.user_principal_name == "alex@willmacdonald.com"
    assert snapshot.display_name == "Alex Morgan"
    assert bearer not in encoded
    assert bearer not in repr(actor)
    assert str(actor.downstream_user_assertion) == "<redacted>"
    with pytest.raises(TypeError):
        json.dumps(actor)
    with pytest.raises(TypeError):
        asdict(actor)  # type: ignore[arg-type]


def test_authenticate_rejects_non_string_and_oversized_tokens(auth_service):
    with pytest.raises(AuthenticationError, match="malformed"):
        auth_service.authenticate(123)  # type: ignore[arg-type]
    with pytest.raises(AuthenticationError, match="too large"):
        auth_service.authenticate("x" * 32769)
