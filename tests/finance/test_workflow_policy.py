import json
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import select, update

from data.domain import CasePurpose, CaseStatus, RuntimeMode
from data.domain.analysis import AnalysisVersion
from data.domain.cases import CaseInstance, WorkflowVersion
from data.domain.decisions import (
    ApprovalTarget,
    CorpusScope,
    Decision,
    StandingAuthorization,
)
from data.domain.execution import ActionPlanningRequested
from data.synthetic.rl001 import (
    OperationalSnapshot,
    build_rl001_evidence,
    instantiate_rl001,
)
from services.analysis.service import (
    AnalyzeCaseCommand,
    analysis_material_hash,
    analyze_case,
)
from services.persistence.sqlite import SqliteStore, build_sqlite_engine, sqlite_store
from services.persistence.store import PersistenceIntegrityError, serialize_model
from services.persistence.tables import (
    analysis_versions,
    case_instances,
    case_projection,
    decisions,
)
from services.policy.evidence import PolicyViolation

FIXTURE = Path(__file__).parent / "fixtures" / "legacy-policy.json"


@pytest.fixture
def raw():
    return json.loads(FIXTURE.read_text())


def build(version=None):
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-POLICY",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=version,
    )
    started = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    command = AnalyzeCaseCommand(
        analysis_id="RL-ANALYSIS-POLICY",
        case=case,
        corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(
            snapshot, analysis_id="RL-ANALYSIS-POLICY", retrieved_at=started
        ),
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=started,
        created_at=started,
        calculation_version="rl001-options-v1",
    )
    return case, snapshot, command


@pytest.mark.parametrize(
    "name,model",
    [
        ("case", CaseInstance),
        ("projected_case", CaseInstance),
        ("analysis", AnalysisVersion),
        ("target", ApprovalTarget),
        ("decision", Decision),
    ],
)
def test_full_legacy_canonical_roundtrip(raw, name, model):
    assert serialize_model(model.model_validate_json(raw[name])) == raw[name]


def test_legacy_hash_and_nested_nulls_remain(raw):
    analysis = AnalysisVersion.model_validate_json(raw["analysis"])
    assert analysis_material_hash(analysis.material) == raw["analysis_material_hash"]
    decision = Decision.model_validate_json(raw["decision"])
    encoded = json.loads(serialize_model(decision))
    assert encoded["rejection_reason"] is None
    assert encoded["actor"]["tenant_id"] is None
    for satisfaction in encoded["approval_satisfactions"]:
        assert "workflow_version" not in satisfaction["target"]["case"]


def test_status_copy_does_not_add_legacy_field(raw):
    case = CaseInstance.model_validate_json(raw["case"])
    changed = case.model_copy(update={"status": CaseStatus.ACTION_PLANNING})
    expected = json.loads(raw["case"])
    expected["status"] = CaseStatus.ACTION_PLANNING.value
    assert json.loads(serialize_model(changed)) == expected
    assert "workflow_version" not in changed.model_dump()
    assert changed.effective_workflow_version is WorkflowVersion.LEGACY


def test_case_version_is_explicit_and_immutable():
    legacy, _, _ = build()
    with pytest.raises(ValueError, match="workflow_version changes require"):
        legacy.model_copy(
            update={"workflow_version": WorkflowVersion.INDEPENDENT_FINANCE}
        )
    changed = legacy.model_copy(
        update={
            "case_id": "RL-CASE-DIFFERENT",
            "workflow_version": WorkflowVersion.INDEPENDENT_FINANCE,
        }
    )
    assert (
        json.loads(serialize_model(changed))["workflow_version"]
        == "independent-finance-v1"
    )
    assert (
        changed.model_copy(
            update={"status": CaseStatus.AWAITING_DECISION}
        ).effective_workflow_version
        is WorkflowVersion.INDEPENDENT_FINANCE
    )


@pytest.mark.parametrize(
    "version,expected,finance",
    [
        (None, "standing-authorization-v1", True),
        (WorkflowVersion.INDEPENDENT_FINANCE, "independent-finance-v1", False),
    ],
)
def test_policy_derives_from_case(version, expected, finance):
    _, _, command = build(version)
    result = analyze_case(command)
    assert result.material.approval_policy_version == expected
    assert (
        any(s.role == "finance_approver" for s in result.approval_satisfactions)
        is finance
    )
    assert (
        any(
            s.role == "finance_approver"
            for s in result.material.standing_authorizations
        )
        is finance
    )
    combined = next(
        o for o in result.response_options if o.option_id == "RL-OPTION-COMBINED"
    )
    assert combined.executable
    assert "finance_approver" in combined.prerequisite_roles
    explicit = analyze_case(
        command.model_copy(update={"approval_policy_version": expected})
    )
    assert serialize_model(explicit) == serialize_model(result)


@pytest.mark.parametrize(
    "version,asserted",
    [
        (None, "independent-finance-v1"),
        (WorkflowVersion.INDEPENDENT_FINANCE, "standing-authorization-v1"),
        (None, "RL-FORGED-APPROVAL-POLICY"),
    ],
)
def test_explicit_wrong_policy_is_rejected(version, asserted):
    _, _, command = build(version)
    with pytest.raises(PolicyViolation, match="Approval policy version"):
        analyze_case(command.model_copy(update={"approval_policy_version": asserted}))


def test_projection_cannot_change_immutable_case_policy(tmp_path):
    case, snapshot, _ = build()
    store = sqlite_store(f"sqlite:///{tmp_path / 'projection.db'}")
    store.create_case(case, snapshot)
    forged = CaseInstance.model_validate(
        {
            **case.model_dump(),
            "workflow_version": WorkflowVersion.INDEPENDENT_FINANCE,
        }
    )
    with pytest.raises(PersistenceIntegrityError):
        store.save_case_projection(forged)
    assert (
        store.get_case(case.case_id).effective_workflow_version
        is WorkflowVersion.LEGACY
    )
    with store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values(payload_json=serialize_model(forged))
        )
    with pytest.raises(PersistenceIntegrityError):
        store.get_projection(case.case_id)
    store.engine.dispose()


@pytest.mark.parametrize(
    "stored_version,analysis_version",
    [
        (WorkflowVersion.INDEPENDENT_FINANCE, None),
        (None, WorkflowVersion.INDEPENDENT_FINANCE),
    ],
)
def test_persistence_rejects_cross_policy_analysis(
    tmp_path, stored_version, analysis_version
):
    stored, snapshot, _ = build(stored_version)
    _, _, command = build(analysis_version)
    store = sqlite_store(f"sqlite:///{tmp_path / 'lineage.db'}")
    store.create_case(stored, snapshot)
    with pytest.raises(PersistenceIntegrityError, match="approval policy"):
        store.save_analysis(analyze_case(command))
    with store.engine.connect() as connection:
        assert connection.execute(select(analysis_versions)).all() == []
    store.engine.dispose()


def test_frozen_legacy_rows_read_from_current_migrated_database(
    tmp_path, raw, monkeypatch
):
    monkeypatch.delenv("SUPPLY_RESPONSE_DATABASE_URL", raising=False)
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    config = Config("migrations/alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    alembic_command.upgrade(config, "head")
    # Deliberately avoid sqlite_store/create_all: migration alone creates schema.
    engine = build_sqlite_engine(url)
    store = SqliteStore(engine, runtime_mode=RuntimeMode.FALLBACK)
    case = CaseInstance.model_validate_json(raw["case"])
    snapshot = OperationalSnapshot.model_validate_json(raw["snapshot"])
    analysis = AnalysisVersion.model_validate_json(raw["analysis"])
    decision = Decision.model_validate_json(raw["decision"])
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    with store.uow_factory() as uow:
        uow.decisions.insert(decision)
        uow.decisions.insert_satisfactions(
            decision.decision_id, decision.approval_satisfactions
        )
        uow.execution.insert_outbox(ActionPlanningRequested.for_decision(decision))
        uow.cases.set_current_decision(case.case_id, decision.decision_id)
        uow.commit()
    with engine.connect() as connection:
        before = tuple(
            connection.scalar(select(table.c.payload_json))
            for table in (case_instances, analysis_versions, decisions)
        )
    assert before == (raw["case"], raw["analysis"], raw["decision"])
    # Reopen, proving reads from persisted raw JSON, not object reuse.
    engine.dispose()
    engine = build_sqlite_engine(url)
    store = SqliteStore(engine, runtime_mode=RuntimeMode.FALLBACK)
    # get_case reads the mutable projection; immutable Case bytes were checked above.
    assert serialize_model(store.get_case(case.case_id)) == raw["projected_case"]
    assert serialize_model(store.get_analysis(analysis.analysis_id)) == raw["analysis"]
    with store.uow_factory() as uow:
        assert (
            serialize_model(uow.decisions.get(decision.decision_id)) == raw["decision"]
        )
    with engine.connect() as connection:
        after = tuple(
            connection.scalar(select(table.c.payload_json))
            for table in (case_instances, analysis_versions, decisions)
        )
    assert after == before
    assert (
        analysis_material_hash(store.get_analysis(analysis.analysis_id).material)
        == raw["analysis_material_hash"]
    )
    engine.dispose()


def test_new_policy_rejects_injected_legacy_finance_material(tmp_path):
    case, snapshot, _ = build(WorkflowVersion.INDEPENDENT_FINANCE)
    _, _, legacy_command = build()
    legacy = analyze_case(legacy_command)
    forged_material = legacy.material.model_copy(
        update={
            "approval_policy_version": "independent-finance-v1",
        }
    )
    forged = legacy.model_copy(
        update={
            "material": forged_material,
            "material_hash": analysis_material_hash(forged_material),
        }
    )
    store = sqlite_store(f"sqlite:///{tmp_path / 'injected.db'}")
    store.create_case(case, snapshot)
    with pytest.raises(PersistenceIntegrityError, match="Finance standing evidence"):
        store.save_analysis(forged)
    store.engine.dispose()


def test_legacy_baseline_rebuild_still_matches_frozen_analysis(raw):
    case = CaseInstance.model_validate_json(raw["case"])
    snapshot = OperationalSnapshot.model_validate_json(raw["snapshot"])
    started = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    result = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-LEGACY-FINANCE-COMPAT",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id="RL-ANALYSIS-LEGACY-FINANCE-COMPAT",
                retrieved_at=started,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=started,
            created_at=started,
            calculation_version="rl001-options-v1",
        )
    )
    assert serialize_model(result) == raw["analysis"]
    assert result.material_hash == raw["analysis_material_hash"]
