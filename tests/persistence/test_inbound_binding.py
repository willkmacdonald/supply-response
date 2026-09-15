from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from data.domain import CaseInstance, CasePurpose, RuntimeMode
from data.domain.inbound import SupplierEmailSource, parse_supplier_disruption
from data.synthetic.rl001 import instantiate_rl001
from services.persistence.sqlite import sqlite_store
from services.persistence.store import (
    ImmutableRecordConflict,
    PersistenceIntegrityError,
)
from services.persistence.tables import case_projection
from tests.domain.test_inbound_email import WILL_BODY


def source():
    return SupplierEmailSource(
        tenant_id="tenant",
        mailbox_object_id="mailbox",
        internet_message_id="<email@example.com>",
        review_fingerprint="a" * 64,
        message_id="provider-id",
        subject="subject",
        sender="will@willmacdonald.com",
        recipients=("agent@willmacdonald.com",),
        received_at=datetime(2026, 9, 14, tzinfo=UTC),
        reviewed_at=datetime(2026, 9, 14, tzinfo=UTC),
        citation_url="https://outlook.office.com/mail/deeplink/read/provider-id",
        facts=parse_supplier_disruption(WILL_BODY),
    )


def bound_case():
    case, snapshot = instantiate_rl001(
        case_id="bound", purpose=CasePurpose.SHOWCASE, runtime_mode=RuntimeMode.LIVE
    )
    return CaseInstance.model_validate(
        {**case.model_dump(), "supplier_email": source()}
    ), snapshot


def test_legacy_serialization_and_binding_model_copy():
    case, _ = instantiate_rl001(
        case_id="legacy", purpose=CasePurpose.SHOWCASE, runtime_mode=RuntimeMode.LIVE
    )
    assert "supplier_email" not in case.model_dump()
    bound, _ = bound_case()
    assert getattr(bound, "supplier_email", None) == source()
    with pytest.raises(ValueError, match="supplier_email"):
        bound.model_copy(update={"supplier_email": None})
    with pytest.raises(ValueError, match="supplier_email"):
        case.model_copy(update={"supplier_email": source()})


def test_persistence_round_trip_and_all_projection_provenance_checks(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'bound.db'}", runtime_mode=RuntimeMode.LIVE
    )
    case, snapshot = bound_case()
    store.create_case(case, snapshot)
    assert getattr(store.get_case(case.case_id), "supplier_email", None) == source()
    forged = CaseInstance.model_validate({**case.model_dump(), "supplier_email": None})
    with pytest.raises((ImmutableRecordConflict, PersistenceIntegrityError)):
        store.save_case_projection(forged)
    with store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values(payload_json=forged.model_dump_json())
        )
    with pytest.raises(PersistenceIntegrityError):
        store.get_case(case.case_id)


def test_case_projection_save_rejects_presenter_run_lineage_change(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'presenter-run-save.db'}",
        runtime_mode=RuntimeMode.LIVE,
    )
    case, snapshot = bound_case()
    case = CaseInstance.model_validate(
        {**case.model_dump(), "presenter_run_id": "RL-RUN-" + "a" * 32}
    )
    store.create_case(case, snapshot)
    changed = CaseInstance.model_validate(
        {**case.model_dump(), "presenter_run_id": "RL-RUN-" + "b" * 32}
    )

    with pytest.raises(ImmutableRecordConflict, match="immutable provenance"):
        store.save_case_projection(changed)


def test_case_projection_read_rejects_presenter_run_lineage_corruption(tmp_path):
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'presenter-run-read.db'}",
        runtime_mode=RuntimeMode.LIVE,
    )
    case, snapshot = bound_case()
    case = CaseInstance.model_validate(
        {**case.model_dump(), "presenter_run_id": "RL-RUN-" + "a" * 32}
    )
    store.create_case(case, snapshot)
    changed = CaseInstance.model_validate(
        {**case.model_dump(), "presenter_run_id": "RL-RUN-" + "b" * 32}
    )
    with store.engine.begin() as connection:
        connection.execute(
            update(case_projection)
            .where(case_projection.c.case_id == case.case_id)
            .values(payload_json=changed.model_dump_json())
        )

    with pytest.raises(PersistenceIntegrityError, match="case projection"):
        store.get_case(case.case_id)
