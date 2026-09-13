import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import CorpusScope, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceProposal, FinanceReviewStatus
from data.domain.proposals import ProposalSelection, SelectionReceipt
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.persistence.sqlite import sqlite_store
from services.persistence.store import serialize_model
from services.persistence.tables import (
    analysis_versions,
    approval_satisfactions,
    case_proposal_selections,
    decisions,
    evidence_items,
    finance_review_revisions,
    outbox_events,
)
from services.policy.finance_review import resolve_finance_review, submit_finance_review

START = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
SUBMITTED = datetime.fromisoformat("2026-09-01T14:02:00+00:00")


def fingerprint(value):
    return hashlib.sha256(serialize_model(value).encode()).hexdigest()


def actor(taylor=False):
    return IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR" if taylor else "RL-PERSONA-ALEX",
        source_id="RL-ENTRA-TAYLOR" if taylor else "RL-ENTRA-ALEX",
        effective_roles=("finance_approver",)
        if taylor
        else ("material_planner", "response_approver"),
        identity_source=IdentitySource.ENTRA,
        tenant_id="11111111-1111-4111-8111-111111111111",
        object_id="33333333-3333-4333-8333-333333333333"
        if taylor
        else "22222222-2222-4222-8222-222222222222",
        display_name="Taylor" if taylor else "Alex",
    )


def build_analysis(case, snapshot, analysis_id):
    return analyze_case(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot, analysis_id=analysis_id, retrieved_at=START
            ),
            analysis_started_at=START,
            created_at=START,
            calculation_version="rl001-options-v1",
        )
    )


@dataclass
class SelectionContext:
    store: object
    case: object
    snapshot: object
    analysis: object
    serial: int = 0
    alex: IdentitySnapshot = field(default_factory=actor)
    taylor: IdentitySnapshot = field(default_factory=lambda: actor(True))

    def state(self):
        with self.store.uow_factory() as uow:
            return uow.proposals.get_state(self.case.case_id)

    def publish_option(self, option_id):
        self.serial += 1
        high = next(
            o for o in self.analysis.response_options if o.option_id == option_id
        ).predicted.response_cost > Decimal(20000)
        command = receipt(
            self,
            option_id,
            f"selection-{self.serial}",
            f"review-{self.serial}" if high else None,
            self.state().token,
            submitted_at=SUBMITTED + timedelta(minutes=2 * self.serial),
        )
        return persist(self, command)

    def publish_combined(self):
        return self.publish_option("RL-OPTION-COMBINED")

    def publish_transfer(self):
        return self.publish_option("RL-OPTION-TRANSFER")


@pytest.fixture
def selection_context(tmp_path):
    store = sqlite_store(f"sqlite:///{tmp_path / 'selection.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-SELECTION",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = build_analysis(case, snapshot, "RL-ANALYSIS-SELECTION-1")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    yield SelectionContext(store, case, snapshot, analysis)
    store.engine.dispose()


def receipt(
    ctx, option_id, selection_id, review_id, expected, *, submitted_at=SUBMITTED
):
    option = next(o for o in ctx.analysis.response_options if o.option_id == option_id)
    selection = ProposalSelection(
        selection_id=selection_id,
        proposal=FinanceProposal(
            case_id=ctx.case.case_id,
            analysis_id=ctx.analysis.analysis_id,
            analysis_material_hash=ctx.analysis.material_hash,
            option_id=option_id,
            response_cost=option.predicted.response_cost,
        ),
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
        submitted_by=ctx.alex,
        submitted_at=submitted_at,
        finance_review_id=review_id,
    )
    material = json.dumps(
        {
            "selection": selection.model_dump(mode="json"),
            "expected": expected.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return SelectionReceipt(
        selection=selection,
        expected=expected,
        idempotency_key=f"publish:{selection_id}",
        request_fingerprint=hashlib.sha256(material.encode()).hexdigest(),
    )


def persist(ctx, command):
    with ctx.store.uow_factory() as uow:
        if command.selection.finance_review_id:
            pending = submit_finance_review(
                review_id=command.selection.finance_review_id,
                proposal=command.selection.proposal,
                actor=command.selection.submitted_by,
                now=command.selection.submitted_at,
            )
            uow.finance_reviews.append(
                pending,
                expected_revision=None,
                idempotency_key=f"pending:{command.selection.selection_id}",
                request_fingerprint=fingerprint(pending),
            )
        result = uow.proposals.publish(command)
        uow.commit()
        return result


def counts(store):
    with store.engine.connect() as connection:
        return {
            table.name: connection.scalar(select(func.count()).select_from(table))
            for table in (
                case_proposal_selections,
                finance_review_revisions,
                analysis_versions,
                evidence_items,
                decisions,
                approval_satisfactions,
                outbox_events,
            )
        }


def test_initial_publication_and_pointer(selection_context):
    ctx = selection_context
    state = ctx.state()
    assert state.token.generation == 1 and state.selection is None
    command = receipt(ctx, "RL-OPTION-COMBINED", "selection-1", "review-1", state.token)
    assert persist(ctx, command) == command.selection
    current = ctx.state()
    assert current.token.generation == 2
    assert current.selection == command.selection
    assert (
        current.review.status is FinanceReviewStatus.PENDING
        and current.review_revision == 1
    )


def test_transfer_replaces_rejected_review_without_new_review(selection_context):
    ctx = selection_context
    first = ctx.publish_combined()
    with ctx.store.uow_factory() as uow:
        state = uow.proposals.get_state(ctx.case.case_id)
        rejected = resolve_finance_review(
            review=state.review,
            current_proposal=state.selection.proposal,
            actor=ctx.taylor,
            approved=False,
            reason="Budget 10000",
            now=first.submitted_at + timedelta(minutes=1),
        )
        uow.finance_reviews.append(
            rejected,
            expected_revision=1,
            idempotency_key="reject-1",
            request_fingerprint="b" * 64,
        )
        uow.proposals.guard_current(ctx.case.case_id, expected=state.token)
        uow.commit()
    second = ctx.publish_transfer()
    state = ctx.state()
    with ctx.store.uow_factory() as uow:
        original = uow.finance_reviews.get_revision(first.finance_review_id, 2)
        superseded, revision = uow.finance_reviews.get_latest(first.finance_review_id)
    assert state.selection == second and state.review is None and original == rejected
    assert (
        superseded.status is FinanceReviewStatus.SUPERSEDED
        and superseded.reason == "Budget 10000"
        and revision == 3
    )


def test_two_selections_have_one_winner(selection_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.exc import IntegrityError, OperationalError

    from services.persistence.proposals import StaleProposal

    ctx = selection_context
    expected = ctx.state().token
    commands = [
        receipt(ctx, "RL-OPTION-TRANSFER", f"race-{i}", None, expected) for i in (1, 2)
    ]
    barrier = Barrier(2)

    def contender(command):
        try:
            barrier.wait(timeout=5)
            return persist(ctx, command)
        except (StaleProposal, IntegrityError) as error:
            return error
        except OperationalError as error:
            if "locked" not in str(error).lower():
                barrier.abort()
                raise
            return error
        except BaseException:
            barrier.abort()
            raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=15)
            for future in [pool.submit(contender, command) for command in commands]
        ]
    winners = [result for result in results if isinstance(result, ProposalSelection)]
    assert len(winners) == 1
    assert ctx.state().selection == winners[0]


def test_late_cas_failure_rolls_back_pending_receipt_and_pointer(
    selection_context, monkeypatch
):
    import services.persistence.proposals as module
    from services.persistence.proposals import StaleProposal

    ctx = selection_context
    before_state, before_counts = ctx.state(), counts(ctx.store)
    command = receipt(
        ctx,
        "RL-OPTION-COMBINED",
        "late-failure",
        "late-review",
        before_state.token,
    )

    def fail_cas(connection, **kwargs):
        assert kwargs
        assert (
            connection.scalar(
                select(func.count()).select_from(case_proposal_selections)
            )
            == 1
        )
        assert (
            connection.scalar(
                select(func.count()).select_from(finance_review_revisions)
            )
            == 1
        )
        raise StaleProposal("injected late CAS failure")

    monkeypatch.setattr(module, "_cas_projection", fail_cas)
    with pytest.raises(StaleProposal):
        persist(ctx, command)
    assert counts(ctx.store) == before_counts
    assert ctx.state() == before_state


def test_new_analysis_invalidates_selection_and_supersedes_review(selection_context):
    ctx = selection_context
    selected = ctx.publish_combined()
    replacement = build_analysis(ctx.case, ctx.snapshot, "RL-ANALYSIS-SELECTION-2")
    assert replacement.material_hash == ctx.analysis.material_hash
    ctx.store.save_analysis(replacement)
    state = ctx.state()
    assert state.token.generation == 3
    assert state.token.analysis_id == replacement.analysis_id
    assert state.selection is None
    with ctx.store.uow_factory() as uow:
        review, revision = uow.finance_reviews.get_latest(selected.finance_review_id)
    assert review.status is FinanceReviewStatus.SUPERSEDED
    assert revision == 2
