import pytest

from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import Orchestrator
from apps.api.app.live import LiveAnalysisApplicationService, LiveSourceUnavailable
from data.domain import CaseInstance, RuntimeMode
from data.domain.evidence import AuthorityScope
from data.domain.inbound import InboundEmailError
from services.analysis.service import analyze_case
from services.persistence.sqlite import sqlite_store
from tests.integration.test_live_case_contract import NOW, FakeWorkIQ
from tests.integration.test_live_hardening import ExplicitLiveOperationalPort
from tests.integration.test_workiq_trust_boundaries import _actor_and_service
from tests.persistence.test_inbound_binding import bound_case


class BoundWorkIQ(FakeWorkIQ):
    seed_calls = 0
    bound_calls = 0
    fail = False

    async def retrieve_supplier_signal(self, **kwargs):
        self.seed_calls += 1
        raise AssertionError("bound email must never use seeded supplier")

    async def retrieve_bound_supplier_signal(self, *, source, **kwargs):
        self.bound_calls += 1
        if self.fail:
            raise InboundEmailError("INBOUND_EMAIL_CHANGED")
        assert source.internet_message_id == "<email@example.com>"
        return self._retrieval(
            {**kwargs, "source_id": "current-moved-locator"},
            "ALPHA",
            AuthorityScope.SUPPLIER_STATEMENT,
        )


def setup(tmp_path, *, conflict=False):
    actor = _actor_and_service()[1]
    store = sqlite_store(
        f"sqlite:///{tmp_path / 'bound-analysis.db'}", runtime_mode=RuntimeMode.LIVE
    )
    case, snapshot = bound_case()
    source = case.supplier_email.model_copy(
        update={"tenant_id": actor.tenant_id, "mailbox_object_id": actor.object_id}
    )
    if conflict:
        source = source.model_copy(
            update={"facts": source.facts.model_copy(update={"partial_quantity": 2000})}
        )
    case = CaseInstance.model_validate({**case.model_dump(), "supplier_email": source})
    store.create_case(case, snapshot)
    workiq = BoundWorkIQ()
    service = LiveAnalysisApplicationService(
        store=store,
        operational_data=ExplicitLiveOperationalPort(),
        work_iq=workiq,
        orchestrator=Orchestrator(LocalAgentSet.deterministic, analyze_case),
        supplier_source_id="seed-locator",
        quality_source_id="source-quality",
        fabric_citation_base_url="https://app.powerbi.com/groups/demo/reports/report",
        clock=lambda: NOW,
    )
    return service, store, workiq, actor


@pytest.mark.anyio
async def test_bound_analysis_uses_current_email_evidence_and_preserves_binding(
    tmp_path,
):
    service, store, workiq, actor = setup(tmp_path)
    analysis = await service.create("bound", actor=actor)
    assert workiq.seed_calls == 0 and workiq.bound_calls == 1
    assert any(
        item.source_id == "current-moved-locator" for item in analysis.evidence_items
    )
    assert analysis.retrieval_lineage[0].source_ids == ("current-moved-locator",)
    assert store.get_case("bound").supplier_email.message_id == "provider-id"


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["source", "fabric"])
async def test_bound_analysis_revalidates_and_never_falls_back(tmp_path, failure):
    service, store, workiq, actor = setup(tmp_path, conflict=failure == "fabric")
    workiq.fail = failure == "source"
    with pytest.raises(LiveSourceUnavailable):
        await service.create("bound", actor=actor)
    assert workiq.seed_calls == 0
    assert store.get_projection("bound").current_analysis_id is None
