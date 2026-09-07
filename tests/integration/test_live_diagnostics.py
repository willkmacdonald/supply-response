from __future__ import annotations

import logging

import pytest

from apps.api.app.live import LiveSourceUnavailable
from data.domain import RuntimeMode
from services.persistence.sqlite import sqlite_store
from tests.integration.test_live_hardening import (
    ExactWorkIQ,
    ExplicitLiveOperationalPort,
    _seed,
    _service,
)
from tests.integration.test_workiq_trust_boundaries import _actor_and_service

SECRET = "Bearer private-token; supplier confidential content"


class BrokenOperational(ExplicitLiveOperationalPort):
    async def retrieve(self, **kwargs):
        raise TimeoutError(SECRET)


class BrokenSupplier(ExactWorkIQ):
    async def retrieve_supplier_signal(self, **kwargs):
        try:
            raise PermissionError(SECRET)
        except PermissionError as error:
            raise RuntimeError(SECRET) from error


class BrokenQuality(ExactWorkIQ):
    async def retrieve_quality_context(self, **kwargs):
        raise TimeoutError(SECRET)


class BrokenOrchestrator:
    async def analyze(self, command):
        raise RuntimeError(SECRET)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("overrides", "stage", "error_type"),
    [
        ({"operational": BrokenOperational()}, "retrieve_fabric", "TimeoutError"),
        ({"work_iq": BrokenSupplier()}, "retrieve_supplier", "RuntimeError"),
        ({"work_iq": BrokenQuality()}, "retrieve_quality", "TimeoutError"),
        (
            {"operational": ExplicitLiveOperationalPort(incomplete=True)},
            "validate_required_evidence",
            "ValueError",
        ),
        ({"orchestrator": BrokenOrchestrator()}, "orchestrate", "RuntimeError"),
    ],
)
async def test_failure_diagnostics_identify_boundary_without_payload(
    tmp_path, caplog, overrides, stage, error_type
):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'diagnostics.db'}", runtime_mode=RuntimeMode.LIVE
    )
    await _seed(store)
    with (
        caplog.at_level(logging.WARNING, logger="apps.api.app.live"),
        pytest.raises(LiveSourceUnavailable) as caught,
    ):
        await _service(store, **overrides).create(
            "RL-CASE-LIVE", actor=_actor_and_service()[1]
        )

    records = [r for r in caplog.records if r.name == "apps.api.app.live"]
    assert any(
        f"stage={stage} " in r.getMessage()
        and f"error_type={error_type} " in r.getMessage()
        and "origin=" in r.getMessage()
        for r in records
    )
    assert all(r.exc_info is None and r.stack_info is None for r in records)
    assert SECRET not in caplog.text
    assert "private-token" not in repr([r.__dict__ for r in records])
    assert "RL-CASE-LIVE" not in caplog.text
    if stage == "retrieve_supplier":
        assert "cause_type=PermissionError" in caplog.text
    assert caught.value.code == "LIVE_SOURCE_UNAVAILABLE"
    assert SECRET not in str(caught.value)
    assert store.get_projection("RL-CASE-LIVE").current_analysis_id is None


@pytest.mark.anyio
async def test_persistence_failure_has_its_own_stage(tmp_path, caplog):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'empty.db'}", runtime_mode=RuntimeMode.LIVE
    )
    with (
        caplog.at_level(logging.WARNING, logger="apps.api.app.live"),
        pytest.raises(LiveSourceUnavailable),
    ):
        await _service(store).create(
            "missing-private-case", actor=_actor_and_service()[1]
        )
    assert "stage=load_case " in caplog.text
    assert "missing-private-case" not in caplog.text


@pytest.mark.anyio
async def test_success_emits_no_failure_diagnostics(tmp_path, caplog):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'success.db'}", runtime_mode=RuntimeMode.LIVE
    )
    await _seed(store)
    with caplog.at_level(logging.WARNING, logger="apps.api.app.live"):
        await _service(store).create("RL-CASE-LIVE", actor=_actor_and_service()[1])
    assert not [r for r in caplog.records if r.name == "apps.api.app.live"]
