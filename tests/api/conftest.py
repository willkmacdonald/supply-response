from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from services.execution.playback import ImmediateClock


@pytest.fixture
def immediate_clock() -> ImmediateClock:
    return ImmediateClock(datetime.now(UTC))


@pytest.fixture
def app(tmp_path, immediate_clock):
    return create_app(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'api.db'}",
        ),
        clock=immediate_clock.now,
        playback_clock=immediate_clock,
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def services(app):
    return app.state.services
