from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from sqlalchemy import Engine

from apps.api.app.live import LiveOperationalRetrieval
from apps.api.app.settings import Settings
from data.domain import CaseInstance, CasePurpose, CaseStatus, RuntimeMode
from integrations.fabric.demo_source import build_rl001_live_source
from scripts import load_fabric_rl001


class FakeEngine:
    def __init__(self) -> None:
        self.connection = object()
        self.begin_calls = 0
        self.connect_calls = 0
        self.dispose_calls = 0

    def begin(self) -> Any:
        self.begin_calls += 1
        return nullcontext(self.connection)

    def connect(self) -> Any:
        self.connect_calls += 1
        return nullcontext(self.connection)

    def dispose(self) -> None:
        self.dispose_calls += 1


def _settings(**changes: Any) -> Settings:
    values = {
        "runtime_mode": RuntimeMode.LIVE,
        "allowed_tenant_id": "11111111-1111-4111-8111-111111111111",
        "fabric_sql_server": "demo.database.fabric.microsoft.com,1433",
        "fabric_sql_database": "SupplyResponseDemo-id",
        "credential_mode": "azure_cli",
        "fabric_citation_base_url": (
            "https://app.powerbi.com/groups/demo/reports/report"
        ),
    }
    values.update(changes)
    return Settings(**values)


def test_dry_run_uses_a_read_only_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = FakeEngine()
    calls = []
    monkeypatch.setattr(
        load_fabric_rl001,
        "ensure_rl001_live_source",
        lambda connection, bundle, *, apply: (
            calls.append((connection, bundle, apply)) or "planned"
        ),
    )

    result = load_fabric_rl001.run(
        apply=False,
        settings=_settings(),
        engine=cast(Engine, engine),
    )

    assert result == "planned"
    assert len(calls) == 1
    assert calls[0][0] is engine.connection
    assert calls[0][2] is False
    assert engine.connect_calls == 1
    assert engine.begin_calls == 0
    assert engine.dispose_calls == 0


def test_apply_keeps_ensure_inside_one_transaction_then_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []

    class TransactionEngine(FakeEngine):
        def begin(self) -> Any:
            self.begin_calls += 1
            connection = self.connection

            class Transaction:
                def __enter__(self):
                    events.append("begin")
                    return connection

                def __exit__(self, *args):
                    events.append("commit" if args[0] is None else "rollback")

            return Transaction()

    engine = TransactionEngine()
    monkeypatch.setattr(
        load_fabric_rl001,
        "ensure_rl001_live_source",
        lambda connection, bundle, *, apply: events.append("ensure") or "inserted",
    )
    monkeypatch.setattr(
        load_fabric_rl001,
        "verify_readback",
        lambda active_engine, bundle: events.append("verify"),
    )

    result = load_fabric_rl001.run(
        apply=True,
        settings=_settings(),
        engine=cast(Engine, engine),
    )

    assert result == "inserted"
    assert events == ["begin", "ensure", "commit", "verify"]
    assert engine.begin_calls == 1
    assert engine.connect_calls == 0


def test_write_failure_rolls_back_and_skips_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []

    class TransactionEngine(FakeEngine):
        def begin(self) -> Any:
            connection = self.connection

            class Transaction:
                def __enter__(self):
                    return connection

                def __exit__(self, exc_type, *args):
                    events.append("rollback" if exc_type else "commit")

            return Transaction()

    def fail_write(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(load_fabric_rl001, "ensure_rl001_live_source", fail_write)
    monkeypatch.setattr(
        load_fabric_rl001,
        "verify_readback",
        lambda *args: events.append("verify"),
    )

    with pytest.raises(RuntimeError, match="write failed"):
        load_fabric_rl001.run(
            apply=True,
            settings=_settings(),
            engine=cast(Engine, TransactionEngine()),
        )

    assert events == ["rollback"]


def test_postcommit_readback_failure_reports_no_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []

    class TransactionEngine(FakeEngine):
        def begin(self) -> Any:
            connection = self.connection

            class Transaction:
                def __enter__(self):
                    return connection

                def __exit__(self, exc_type, *args):
                    events.append("rollback" if exc_type else "commit")

            return Transaction()

    monkeypatch.setattr(
        load_fabric_rl001,
        "ensure_rl001_live_source",
        lambda *args, **kwargs: "inserted",
    )
    monkeypatch.setattr(
        load_fabric_rl001,
        "verify_readback",
        lambda *args: (_ for _ in ()).throw(RuntimeError("wrong payload")),
    )

    with pytest.raises(RuntimeError, match="committed.*verification failed"):
        load_fabric_rl001.run(
            apply=True,
            settings=_settings(),
            engine=cast(Engine, TransactionEngine()),
        )

    assert events == ["commit"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"runtime_mode": RuntimeMode.FALLBACK, "database_url": "sqlite://"},
            "live runtime",
        ),
        ({"credential_mode": "managed_identity"}, "Azure CLI credential"),
        ({"fabric_citation_base_url": None}, "citation base"),
    ],
)
def test_rejects_an_unsafe_local_loader_environment(changes, message) -> None:
    engine = FakeEngine()

    with pytest.raises(SystemExit, match=message):
        load_fabric_rl001.run(
            apply=False,
            settings=_settings(**changes),
            engine=cast(Engine, engine),
        )

    assert engine.connect_calls == 0
    assert engine.begin_calls == 0


def test_invalid_citation_fails_before_engine_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        load_fabric_rl001,
        "build_fabric_engine",
        lambda *args: pytest.fail("engine must not be built"),
    )

    with pytest.raises(ValueError, match="trusted policy"):
        load_fabric_rl001.run(
            apply=False,
            settings=_settings(fabric_citation_base_url="https://evil.example/report"),
        )


def test_owned_engine_and_credential_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine()

    class Credential:
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    credential = Credential()
    monkeypatch.setattr(
        load_fabric_rl001, "build_credential", lambda settings: credential
    )
    monkeypatch.setattr(load_fabric_rl001, "build_fabric_engine", lambda *args: engine)
    monkeypatch.setattr(
        load_fabric_rl001,
        "ensure_rl001_live_source",
        lambda *args, **kwargs: "planned",
    )

    assert load_fabric_rl001.run(apply=False, settings=_settings()) == "planned"
    assert engine.dispose_calls == 1
    assert credential.close_calls == 1


def test_main_bounds_errors_without_echoing_sensitive_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["load_fabric_rl001.py"])
    monkeypatch.setattr(
        load_fabric_rl001,
        "run",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("server=tcp:secret;token=do-not-print")
        ),
    )
    monkeypatch.setattr(load_fabric_rl001, "Settings", lambda: _settings())

    assert load_fabric_rl001.main() == 1
    captured = capsys.readouterr()
    assert "configuration, identity, or SQL operation failed" in captured.err
    assert "secret" not in captured.err
    assert captured.out == ""


def _retrieval_with_rebound_fields(bundle, **evidence_changes):
    retrieved_at = datetime(2026, 9, 6, tzinfo=UTC)
    case_id = "RL-CASE-LOADER-VERIFY"
    analysis_id = "RL-ANALYSIS-LOADER-VERIFY"
    snapshot = bundle.snapshot().model_copy(update={"case_id": case_id})
    evidence = tuple(
        item.model_copy(
            update={
                "case_id": case_id,
                "retrieved_for_analysis_id": analysis_id,
                "retrieved_at": retrieved_at,
                "runtime_mode": RuntimeMode.LIVE,
                **evidence_changes,
            }
        )
        for item in bundle.evidence()
    )
    return LiveOperationalRetrieval(
        case=CaseInstance(
            case_id=case_id,
            template_id="RL-001",
            purpose=CasePurpose.SHOWCASE,
            runtime_mode=RuntimeMode.LIVE,
            scenario_effective_time=snapshot.scenario_effective_time,
            status=CaseStatus.OPEN,
        ),
        snapshot=snapshot,
        evidence=evidence,
        source_snapshot_id=bundle.source_snapshot_id,
        retrieved_at=retrieved_at,
    )


def test_verify_readback_compares_every_normalized_evidence_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    retrieval = _retrieval_with_rebound_fields(bundle, claim="tampered")
    monkeypatch.setattr(load_fabric_rl001, "_retrieve", lambda engine: retrieval)

    with pytest.raises(RuntimeError, match="evidence"):
        load_fabric_rl001.verify_readback(cast(Engine, FakeEngine()), bundle)


def test_verify_readback_requires_exactly_one_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    monkeypatch.setattr(
        load_fabric_rl001,
        "_retrieve",
        lambda engine: _retrieval_with_rebound_fields(bundle),
    )

    class CountResult:
        def scalar_one(self):
            return 2

    class StoredResult:
        def mappings(self):
            return self

        def one_or_none(self):
            return bundle.parameters()

    class CountConnection:
        def execute(self, statement, *args, **kwargs):
            if "COUNT(*)" in str(statement):
                return CountResult()
            return StoredResult()

    engine = FakeEngine()
    engine.connection = CountConnection()

    with pytest.raises(RuntimeError, match="exactly one"):
        load_fabric_rl001.verify_readback(cast(Engine, engine), bundle)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("template_id", "RL-TAMPERED"),
        ("effective_at", datetime(2026, 9, 1, 15, 0, tzinfo=UTC)),
    ],
)
def test_verify_readback_rejects_tampered_stored_metadata(
    monkeypatch: pytest.MonkeyPatch,
    column: str,
    value: object,
) -> None:
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )
    monkeypatch.setattr(
        load_fabric_rl001,
        "_retrieve",
        lambda engine: _retrieval_with_rebound_fields(bundle),
    )
    stored_row = {
        **bundle.parameters(),
        column: value,
    }

    class StoredResult:
        def mappings(self):
            return self

        def one_or_none(self):
            return stored_row

        def scalar_one(self):
            return 1

    class StoredConnection:
        def execute(self, *args, **kwargs):
            return StoredResult()

    engine = FakeEngine()
    engine.connection = StoredConnection()

    with pytest.raises(RuntimeError, match="canonical bundle"):
        load_fabric_rl001.verify_readback(cast(Engine, engine), bundle)
