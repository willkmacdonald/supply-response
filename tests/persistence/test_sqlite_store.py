import json
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.exc import IntegrityError

from apps.api.app.settings import Settings
from data.domain import CaseInstance, CasePurpose, CaseStatus, RuntimeMode
from data.domain.analysis import AnalysisRetrievalLineage
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.synthetic.rl001 import (
    SCENARIO_EFFECTIVE_TIME,
    build_rl001_evidence,
    instantiate_rl001,
)
from services.analysis.service import (
    AnalyzeCaseCommand,
    analysis_material_hash,
    analyze_case,
)
from services.persistence.ports import CaseStore
from services.persistence.sqlite import sqlite_store
from services.persistence.store import (
    ImmutableRecordConflict,
    PersistenceIntegrityError,
    RuntimeModeConflict,
    build_store,
    serialize_model,
)
from services.persistence.tables import (
    analysis_versions,
    case_instances,
    case_projection,
    evidence_items,
    metadata,
)


def fallback_rl001_case(case_id: str):
    return instantiate_rl001(
        case_id=case_id,
        purpose=CasePurpose.SHOWCASE,
        runtime_mode=RuntimeMode.FALLBACK,
    )


def fallback_rl001_analysis(case, snapshot, analysis_id: str):
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    return analyze_case(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id=analysis_id,
                retrieved_at=started_at,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=started_at,
            created_at=started_at,
            calculation_version="rl001-options-v1",
        )
    )


def test_sqlite_case_survives_store_reconstruction(tmp_path):
    url = f"sqlite:///{tmp_path / 'supply-response.db'}"
    first = sqlite_store(url)
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-1")
    first.create_case(case, snapshot)

    second = sqlite_store(url)
    restored = second.get_case(case.case_id)
    assert restored == case


def test_store_rejects_runtime_mode_change(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'mode.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-2")
    store.create_case(case, snapshot)
    conflicting = CaseInstance.model_validate(
        {
            **case.model_dump(mode="python"),
            "runtime_mode": RuntimeMode.LIVE,
        }
    )

    with pytest.raises(RuntimeModeConflict):
        store.save_case_projection(conflicting)


def test_case_model_still_rejects_runtime_mode_change():
    case, _ = fallback_rl001_case("RL-CASE-PERSIST-MODEL-GUARD")

    with pytest.raises(ValueError, match="runtime_mode changes require"):
        case.model_copy(update={"runtime_mode": RuntimeMode.LIVE})


def test_settings_load_prefixed_fallback_environment(monkeypatch):
    monkeypatch.setenv("SUPPLY_RESPONSE_RUNTIME_MODE", "fallback")
    monkeypatch.setenv("SUPPLY_RESPONSE_DATABASE_URL", "sqlite:///runtime.db")
    monkeypatch.setenv("UNRELATED_SETTING", "ignored")

    settings = Settings()

    assert settings.runtime_mode is RuntimeMode.FALLBACK
    assert settings.database_url == "sqlite:///runtime.db"
    assert settings.scenario_effective_time == SCENARIO_EFFECTIVE_TIME
    assert settings.tenant_domain == "willmacdonald.com"
    assert settings.frontend_origin == "http://localhost:5173"


def test_settings_reject_live_mode_without_tenant_id():
    with pytest.raises(
        ValidationError,
        match="live mode requires SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
    ):
        Settings(runtime_mode=RuntimeMode.LIVE, database_url="sqlite:///live.db")


def test_serialization_preserves_complete_canonical_money_json():
    _, snapshot = fallback_rl001_case("RL-CASE-PERSIST-JSON")

    serialized = serialize_model(snapshot)
    payload = json.loads(serialized)

    assert serialized == snapshot.model_dump_json(exclude_none=False, by_alias=True)
    assert payload["alpha_expedite"]["incremental_cost_per_unit"] == "7.50"
    assert payload["transfer"]["incremental_cost_per_unit"] == "1.50"
    assert payload["disruption"]["partial_due_date"] is None


def test_shared_metadata_defines_closed_loop_schema():
    assert set(metadata.tables) == {
        "action_projection",
        "analysis_versions",
        "analysis_claims",
        "approval_satisfactions",
        "case_instances",
        "case_projection",
        "decisions",
        "draft_artifacts",
        "evidence_items",
        "execution_actions",
        "execution_attempts",
        "execution_events",
        "finance_review_revisions",
        "operational_snapshots",
        "outbox_events",
        "outcome_observations",
        "playbacks",
    }


def test_decision_scoped_tables_enforce_decision_references():
    for table_name in (
        "action_projection",
        "draft_artifacts",
        "execution_attempts",
        "execution_events",
        "outbox_events",
        "outcome_observations",
        "playbacks",
    ):
        decision_id = metadata.tables[table_name].c.decision_id
        assert {item.target_fullname for item in decision_id.foreign_keys} == {
            "decisions.decision_id"
        }


def test_case_projection_current_pointers_enforce_immutable_references():
    assert {
        item.target_fullname
        for item in case_projection.c.current_analysis_id.foreign_keys
    } == {"analysis_versions.analysis_id"}
    assert {
        item.target_fullname
        for item in case_projection.c.current_decision_id.foreign_keys
    } == {"decisions.decision_id"}


def test_sqlite_store_creates_shared_schema(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'schema.db'}")

    assert set(inspect(store.engine).get_table_names()) == set(metadata.tables)


@pytest.mark.parametrize(
    "column_name",
    ("current_analysis_id", "current_decision_id"),
)
def test_case_projection_rejects_dangling_current_pointers(tmp_path, column_name):
    store = sqlite_store(f"sqlite:///{tmp_path / f'{column_name}.db'}")
    case, snapshot = fallback_rl001_case(f"RL-CASE-{column_name.upper()}")
    store.create_case(case, snapshot)

    with pytest.raises(IntegrityError), store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values({column_name: "RL-MISSING"})
        )


def test_file_sqlite_configures_foreign_keys_busy_timeout_and_wal(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'pragmas.db'}")

    with (
        store.engine.connect() as first_connection,
        store.engine.connect() as second_connection,
    ):
        for connection in (first_connection, second_connection):
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert (
                connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5000
            )
            assert (
                connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
            )


def test_memory_sqlite_avoids_wal_but_keeps_safety_pragmas():
    store = sqlite_store("sqlite:///:memory:")

    with store.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5000
        assert (
            connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "memory"
        )


def test_build_store_binds_the_configured_runtime_mode(tmp_path):
    store = build_store(
        Settings(
            runtime_mode=RuntimeMode.FALLBACK,
            database_url=f"sqlite:///{tmp_path / 'configured.db'}",
        )
    )
    assert isinstance(store, CaseStore)
    live_case, live_snapshot = instantiate_rl001(
        case_id="RL-CASE-PERSIST-LIVE",
        purpose=CasePurpose.SHOWCASE,
        runtime_mode=RuntimeMode.LIVE,
    )

    with pytest.raises(RuntimeModeConflict):
        store.create_case(live_case, live_snapshot)


def test_case_projection_updates_without_rewriting_immutable_case(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'projection.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-PROJECTION")
    store.create_case(case, snapshot)
    updated = case.model_copy(update={"status": CaseStatus.ANALYZING})

    store.save_case_projection(updated)

    with store.engine.connect() as connection:
        immutable_json = connection.execute(
            select(case_instances.c.payload_json).where(
                case_instances.c.case_id == case.case_id
            )
        ).scalar_one()
        projection_json = connection.execute(
            select(case_projection.c.payload_json).where(
                case_projection.c.case_id == case.case_id
            )
        ).scalar_one()
    assert immutable_json == serialize_model(case)
    assert projection_json == serialize_model(updated)
    assert store.get_case(case.case_id) == updated


def test_case_projection_rejects_immutable_provenance_change(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'case-provenance.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-PROVENANCE")
    store.create_case(case, snapshot)
    conflicting = case.model_copy(update={"template_id": "RL-OTHER"})

    with pytest.raises(ImmutableRecordConflict, match="immutable provenance"):
        store.save_case_projection(conflicting)


def test_get_case_rejects_tampered_projection_provenance(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'case-read-integrity.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-READ-INTEGRITY")
    store.create_case(case, snapshot)
    tampered = case.model_copy(update={"template_id": "RL-TAMPERED"})
    with store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values(payload_json=serialize_model(tampered))
        )

    with pytest.raises(PersistenceIntegrityError, match="case projection"):
        store.get_case(case.case_id)


def test_list_cases_filters_by_purpose(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'list.db'}")
    showcase, showcase_snapshot = fallback_rl001_case("RL-CASE-PERSIST-SHOWCASE")
    automated, automated_snapshot = instantiate_rl001(
        case_id="RL-CASE-PERSIST-AUTOMATED",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    store.create_case(showcase, showcase_snapshot)
    store.create_case(automated, automated_snapshot)

    assert store.list_cases(purpose=CasePurpose.SHOWCASE) == (showcase,)
    assert store.list_cases() == (automated, showcase)


def test_list_cases_rejects_runtime_index_filter_evasion(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'list-runtime-tamper.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-LIST-RUNTIME-TAMPER")
    store.create_case(case, snapshot)
    with store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values(runtime_mode=RuntimeMode.LIVE.value)
        )

    with pytest.raises(PersistenceIntegrityError, match="case projection"):
        store.list_cases()


def test_list_cases_rejects_purpose_index_filter_evasion(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'list-purpose-tamper.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-LIST-PURPOSE-TAMPER")
    store.create_case(case, snapshot)
    with store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values(purpose=CasePurpose.AUTOMATED_TEST.value)
        )

    with pytest.raises(PersistenceIntegrityError, match="case projection"):
        store.list_cases(purpose=CasePurpose.SHOWCASE)


def test_analysis_survives_reconstruction_with_nested_records(tmp_path):
    url = f"sqlite:///{tmp_path / 'analysis.db'}"
    first = sqlite_store(url)
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-ANALYSIS")
    analysis = fallback_rl001_analysis(
        case,
        snapshot,
        "RL-ANALYSIS-PERSIST-1",
    )
    first.create_case(case, snapshot)
    first.save_analysis(analysis)

    second = sqlite_store(url)

    assert second.get_analysis(analysis.analysis_id) == analysis
    with second.engine.connect() as connection:
        analysis_json = connection.execute(
            select(analysis_versions.c.payload_json).where(
                analysis_versions.c.analysis_id == analysis.analysis_id
            )
        ).scalar_one()
        evidence_count = connection.execute(
            select(evidence_items.c.evidence_id).where(
                evidence_items.c.analysis_id == analysis.analysis_id
            )
        ).all()
    assert analysis_json == serialize_model(analysis)
    assert len(evidence_count) == len(analysis.evidence_items)
    assert '"maximum_response_cost":"25000.00"' in analysis_json


def test_analysis_versions_are_insert_only(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'immutable-analysis.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-IMMUTABLE")
    analysis = fallback_rl001_analysis(
        case,
        snapshot,
        "RL-ANALYSIS-PERSIST-IMMUTABLE",
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)

    with pytest.raises(ImmutableRecordConflict):
        store.save_analysis(analysis)


def test_stored_a2a_lineage_without_protocol_fields_remains_readable(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'legacy-a2a-lineage.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-LEGACY-LINEAGE")
    analysis = fallback_rl001_analysis(
        case,
        snapshot,
        "RL-ANALYSIS-LEGACY-LINEAGE",
    ).model_copy(
        update={
            "retrieval_lineage": (
                AnalysisRetrievalLineage(
                    source_kind="supplier",
                    context_id="legacy-context",
                    task_id="legacy-task",
                    artifact_ids=("legacy-artifact",),
                    source_ids=("legacy-source",),
                ),
            )
        }
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    with store.engine.begin() as connection:
        payload = json.loads(
            connection.scalar(
                select(analysis_versions.c.payload_json).where(
                    analysis_versions.c.analysis_id == analysis.analysis_id
                )
            )
        )
        payload["retrieval_lineage"][0].pop("protocol")
        payload["retrieval_lineage"][0].pop("request_ids")
        connection.execute(
            update(analysis_versions)
            .where(analysis_versions.c.analysis_id == analysis.analysis_id)
            .values(payload_json=json.dumps(payload))
        )

    lineage = store.get_analysis(analysis.analysis_id).retrieval_lineage[0]
    assert lineage.protocol == "a2a"
    assert lineage.request_ids == ()


def test_analysis_rejects_nested_runtime_provenance_change(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'analysis-mode.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-ANALYSIS-MODE")
    analysis = fallback_rl001_analysis(
        case,
        snapshot,
        "RL-ANALYSIS-PERSIST-MODE",
    )
    changed_evidence = analysis.material.evidence[0].model_copy(
        update={"runtime_mode": RuntimeMode.LIVE}
    )
    changed_material = analysis.material.model_copy(
        update={
            "evidence": (
                changed_evidence,
                *analysis.material.evidence[1:],
            )
        }
    )
    conflicting = analysis.model_copy(
        update={
            "material": changed_material,
            "material_hash": analysis_material_hash(changed_material),
        }
    )
    store.create_case(case, snapshot)

    with pytest.raises(RuntimeModeConflict):
        store.save_analysis(conflicting)


def test_analysis_rejects_material_hash_mismatch(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'analysis-hash.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-ANALYSIS-HASH")
    analysis = fallback_rl001_analysis(
        case,
        snapshot,
        "RL-ANALYSIS-PERSIST-HASH",
    )
    changed_material = analysis.material.model_copy(
        update={"calculation_version": "forged-calculation"}
    )
    conflicting = analysis.model_copy(update={"material": changed_material})
    store.create_case(case, snapshot)

    with pytest.raises(PersistenceIntegrityError, match="material_hash"):
        store.save_analysis(conflicting)


def test_analysis_rejects_stored_snapshot_mismatch_with_valid_hash(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'analysis-snapshot.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-ANALYSIS-SNAPSHOT")
    analysis = fallback_rl001_analysis(
        case,
        snapshot,
        "RL-ANALYSIS-PERSIST-SNAPSHOT",
    )
    forged_snapshot = json.loads(analysis.material.operational_snapshot_json)
    forged_snapshot["analysis_horizon_end"] = "2026-09-30"
    changed_material = analysis.material.model_copy(
        update={
            "operational_snapshot_json": json.dumps(
                forged_snapshot,
                sort_keys=True,
                separators=(",", ":"),
            )
        }
    )
    conflicting = analysis.model_copy(
        update={
            "material": changed_material,
            "material_hash": analysis_material_hash(changed_material),
        }
    )
    store.create_case(case, snapshot)

    with pytest.raises(PersistenceIntegrityError, match="Operational Snapshot"):
        store.save_analysis(conflicting)


def test_get_analysis_rejects_tampered_material_hash(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'analysis-read-hash.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-READ-HASH")
    analysis = fallback_rl001_analysis(case, snapshot, "RL-ANALYSIS-READ-HASH")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    changed_material = analysis.material.model_copy(
        update={"calculation_version": "tampered-calculation"}
    )
    tampered = analysis.model_copy(update={"material": changed_material})
    with store.engine.begin() as connection:
        connection.execute(
            update(analysis_versions)
            .where(analysis_versions.c.analysis_id == analysis.analysis_id)
            .values(payload_json=serialize_model(tampered))
        )

    with pytest.raises(PersistenceIntegrityError, match="material_hash"):
        store.get_analysis(analysis.analysis_id)


def test_get_analysis_rejects_tampered_snapshot_with_valid_hash(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'analysis-read-snapshot.db'}")
    case, snapshot = fallback_rl001_case("RL-CASE-PERSIST-READ-SNAPSHOT")
    analysis = fallback_rl001_analysis(case, snapshot, "RL-ANALYSIS-READ-SNAPSHOT")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    forged_snapshot = json.loads(analysis.material.operational_snapshot_json)
    forged_snapshot["analysis_horizon_end"] = "2026-09-30"
    changed_material = analysis.material.model_copy(
        update={
            "operational_snapshot_json": json.dumps(
                forged_snapshot,
                sort_keys=True,
                separators=(",", ":"),
            )
        }
    )
    changed_hash = analysis_material_hash(changed_material)
    tampered = analysis.model_copy(
        update={"material": changed_material, "material_hash": changed_hash}
    )
    with store.engine.begin() as connection:
        connection.execute(
            update(analysis_versions)
            .where(analysis_versions.c.analysis_id == analysis.analysis_id)
            .values(
                material_hash=changed_hash,
                payload_json=serialize_model(tampered),
            )
        )

    with pytest.raises(PersistenceIntegrityError, match="Operational Snapshot"):
        store.get_analysis(analysis.analysis_id)


def test_alembic_upgrade_and_downgrade_manage_shared_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = Config("migrations/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {
        *metadata.tables,
        "alembic_version",
    }
    projection_foreign_keys = {
        (tuple(item["constrained_columns"]), item["referred_table"]): item
        for item in inspect(engine).get_foreign_keys("case_projection")
    }
    assert (("current_analysis_id",), "analysis_versions") in projection_foreign_keys
    assert (("current_decision_id",), "decisions") in projection_foreign_keys
    assert (
        projection_foreign_keys[(("current_analysis_id",), "analysis_versions")][
            "options"
        ]["ondelete"]
        == "RESTRICT"
    )
    assert (
        projection_foreign_keys[(("current_decision_id",), "decisions")]["options"][
            "ondelete"
        ]
        == "RESTRICT"
    )

    assert {
        item["name"] for item in inspect(engine).get_unique_constraints("outbox_events")
    } >= {"uq_outbox_event_per_decision"}
    assert {
        item["name"] for item in inspect(engine).get_unique_constraints("playbacks")
    } >= {"uq_playback_per_decision"}
    assert {
        item["name"]
        for item in inspect(engine).get_check_constraints("outcome_observations")
    } >= {"ck_outcome_observations_observation_kind_synthetic_provenance"}

    migrated_store = sqlite_store(database_url)
    case, snapshot = fallback_rl001_case("RL-CASE-MIGRATED-FOREIGN-KEYS")
    migrated_store.create_case(case, snapshot)
    for column_name in ("current_analysis_id", "current_decision_id"):
        with pytest.raises(IntegrityError), migrated_store.engine.begin() as connection:
            connection.execute(
                update(case_projection)
                .where(case_projection.c.case_id == case.case_id)
                .values({column_name: "RL-MISSING"})
            )
    migrated_store.engine.dispose()

    command.downgrade(config, "base")

    assert inspect(engine).get_table_names() == ["alembic_version"]


def test_alembic_upgrade_path_adds_pointer_foreign_keys_after_original_0001(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'upgrade-path.db'}"
    config = Config("migrations/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "0001_closed_loop_schema")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "0001_closed_loop_schema"
        )
    original_foreign_keys = {
        tuple(item["constrained_columns"])
        for item in inspect(engine).get_foreign_keys("case_projection")
    }
    assert ("current_analysis_id",) not in original_foreign_keys
    assert ("current_decision_id",) not in original_foreign_keys
    original_store = sqlite_store(database_url)
    original_case, original_snapshot = fallback_rl001_case("RL-CASE-ORIGINAL-0001")
    original_store.create_case(original_case, original_snapshot)
    original_store.engine.dispose()

    command.upgrade(config, "head")

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "0007_finance_review_revisions"
        )
    head_foreign_keys = {
        tuple(item["constrained_columns"])
        for item in inspect(engine).get_foreign_keys("case_projection")
    }
    assert ("current_analysis_id",) in head_foreign_keys
    assert ("current_decision_id",) in head_foreign_keys
    assert {
        item["name"] for item in inspect(engine).get_unique_constraints("outbox_events")
    } >= {"uq_outbox_event_per_decision"}
    assert {
        item["name"] for item in inspect(engine).get_unique_constraints("playbacks")
    } >= {"uq_playback_per_decision"}
    assert {item["name"] for item in inspect(engine).get_columns("playbacks")} >= {
        "failed_at",
        "error_code",
    }
    migrated_store = sqlite_store(database_url)
    assert migrated_store.get_case(original_case.case_id) == original_case
    assert migrated_store.list_cases() == (original_case,)
    case, snapshot = fallback_rl001_case("RL-CASE-UPGRADE-PATH")
    migrated_store.create_case(case, snapshot)
    for column_name in ("current_analysis_id", "current_decision_id"):
        with pytest.raises(IntegrityError), migrated_store.engine.begin() as connection:
            connection.execute(
                update(case_projection)
                .where(case_projection.c.case_id == case.case_id)
                .values({column_name: "RL-MISSING"})
            )
    migrated_store.engine.dispose()

    command.downgrade(config, "0001_closed_loop_schema")

    downgraded_foreign_keys = {
        tuple(item["constrained_columns"])
        for item in inspect(engine).get_foreign_keys("case_projection")
    }
    assert ("current_analysis_id",) not in downgraded_foreign_keys
    assert ("current_decision_id",) not in downgraded_foreign_keys
    assert "uq_outbox_event_per_decision" not in {
        item["name"] for item in inspect(engine).get_unique_constraints("outbox_events")
    }

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]


def test_initial_migration_is_frozen_from_runtime_metadata():
    revision = Path("migrations/versions/0001_closed_loop_schema.py").read_text(
        encoding="utf-8"
    )

    assert "services.persistence.tables" not in revision


def test_pointer_migration_is_frozen_from_runtime_metadata():
    revision = Path(
        "migrations/versions/0002_case_projection_pointer_fks.py"
    ).read_text(encoding="utf-8")

    assert "services.persistence.tables" not in revision


def test_outbox_uniqueness_migration_is_frozen_from_runtime_metadata():
    revision = Path("migrations/versions/0003_outbox_one_planning_event.py").read_text(
        encoding="utf-8"
    )

    assert "services.persistence.tables" not in revision
