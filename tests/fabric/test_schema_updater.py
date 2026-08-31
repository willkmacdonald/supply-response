from __future__ import annotations

import io

import pytest

from fabric.schemas import update_microsoft_schemas as updater


class _Response:
    def __init__(self, final_url: str, payload: bytes = b"{}") -> None:
        self._final_url = final_url
        self._payload = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def geturl(self) -> str:
        return self._final_url

    def read(self) -> bytes:
        return self._payload.read()


@pytest.mark.parametrize(
    "url",
    (
        "http://developer.microsoft.com/schema.json",
        "https://example.com/schema.json",
        "https://developer.microsoft.com:444/schema.json",
        "https://user@developer.microsoft.com/schema.json",
        "https://developer.microsoft.com/schema.json?query=1",
        "https://developer.microsoft.com/schema.json#fragment",
    ),
)
def test_schema_updater_rejects_untrusted_request_urls(monkeypatch, url: str) -> None:
    called = False

    def fake_urlopen(*_args, **_kwargs):
        nonlocal called
        called = True
        return _Response(url)

    monkeypatch.setattr(updater, "urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="Microsoft HTTPS schema URL"):
        updater._fetch(url)
    assert called is False


@pytest.mark.parametrize(
    "final_url",
    (
        "https://developer.microsoft.com/redirected-schema.json",
        "https://example.com/schema.json",
        "http://developer.microsoft.com/schema.json",
        "https://developer.microsoft.com:444/schema.json",
    ),
)
def test_schema_updater_rejects_redirects_and_untrusted_final_urls(
    monkeypatch, final_url: str
) -> None:
    requested = "https://developer.microsoft.com/schema.json"
    monkeypatch.setattr(
        updater,
        "urlopen",
        lambda *_args, **_kwargs: _Response(final_url),
    )

    with pytest.raises(ValueError, match="final URL|Microsoft HTTPS schema URL"):
        updater._fetch(requested)


def test_schema_updater_accepts_exact_default_port_final_url(monkeypatch) -> None:
    requested = "https://developer.microsoft.com:443/schema.json"
    monkeypatch.setattr(
        updater,
        "urlopen",
        lambda *_args, **_kwargs: _Response(requested),
    )

    assert updater._fetch(requested) == {}
