# Proposal-Bound Final Alex Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the exact configured Alex approve or reject current independent-Finance proposal state while atomically recording immutable proposal/review evidence, Decision rows, prerequisite satisfactions, case projection changes, and the single approved outbox event.

**Architecture:** One coherent domain/service/persistence increment adds proposal-bound evidence to Decision JSON without a schema change, adds an exact-identity `FinanceDecisionService`, and adds atomic current-proposal withdrawal for Alex rejection. Legacy recording remains byte-for-byte compatible and rejects independent-policy cases; historical validation follows exact stored selection/review revisions rather than mutable current state.

**Tech Stack:** Python 3.12, Pydantic v2 frozen models, SQLAlchemy Core, existing UoW/SQLite/Fabric-compatible repositories, pytest, Pyright, Ruff.

## Global Constraints

- Consumes accepted Finance query commit `6dcfe5f`. Parent documentation checkpoint is `a450fac`; record the actual post-plan HEAD as the implementation dispatch base.
- This is one reviewable task because domain, policy, service, and persistence invariants must land together.
- No API, route, UI, schema, migration, mail, deployment, execution activation, or live call.
- Never modify `tests/finance/fixtures/legacy-policy.json`; its Decision JSON remains byte-for-byte identical.
- Every pytest command includes `-m 'not fabric_live' -o addopts=''`.
- Exact Alex authorization occurs before every initial, replay, and recovery UoW.
- Historical evidence compares exact immutable selection and referenced review revision, never latest/current state.
- `withdraw_current` requires aware `now` and `now >= selection.submitted_at` even for low-cost selections.
- A later execution-currentness guard is mandatory before independent cases can be route-activated.

---

### Task 1: Proposal-Bound Finalization and Transactional Withdrawal

**Files:**
- Create: `data/domain/finance_decisions.py`
- Modify: `data/domain/decisions.py`
- Modify: `services/decisions/service.py`
- Modify: `services/finance/contracts.py`
- Create: `services/finance/decisions.py`
- Modify: `services/persistence/ports.py`
- Modify: `services/persistence/proposals.py`
- Modify: `services/persistence/store.py`
- Create: `tests/finance/test_finance_final_decision.py`
- Modify: `tests/finance/test_workflow_policy.py`
- Modify: `tests/persistence/test_decision_outbox.py`
- Verify unchanged: `tests/finance/fixtures/legacy-policy.json`

**Interfaces:**
- Consumes: accepted `BoundFinanceActors`, Finance command/query service, Proposal/FinanceReview/Decision repositories, `DecisionPolicy`, case projection methods, UoW, and `ActionPlanningRequested.for_decision`.
- Produces: `ProposalApprovalEvidence`; optional `Decision.proposal_approval`; `FinalizeProposalCommand`; `FinanceDecisionService.finalize(command: FinalizeProposalCommand, actor: IdentitySnapshot) -> Decision`; `DecisionPolicy.authorize_independent_and_materialize(command, actor, case, projection, analysis, proposal_approval) -> tuple[ApprovalSatisfaction, ...]`; `ProposalStore.withdraw_current(case_id: str, *, expected: ProposalToken, now: datetime, operation_id: str) -> ProposalToken`.

- [ ] **Step 1: Write failing domain and frozen-compatibility tests**

Create the focused test file with a real file-SQLite independent case, saved analysis, accepted `FinanceService`, configured Alex/Taylor, and deterministic aware clocks. Copy the concrete fixture construction from `tests/finance/test_finance_service.py`; do not import another test module's fixture.

```python
def test_evidence_requires_exact_approved_revision(final_ctx):
    submitted = submit_and_approve(final_ctx)
    evidence = ProposalApprovalEvidence(
        selection=submitted.selection,
        review=submitted.resolution.review,
        review_revision=submitted.resolution.review_revision,
    )
    assert evidence.review.status is FinanceReviewStatus.APPROVED
    for changed in (
        {"review": None},
        {"review_revision": None},
        {"review_revision": 1},
        {"review": evidence.review.model_copy(update={"status": FinanceReviewStatus.REJECTED, "reason": "no"})},
        {"review": evidence.review.model_copy(update={"proposal": evidence.review.proposal.model_copy(update={"option_id": "other"})})},
    ):
        with pytest.raises(ValidationError):
            ProposalApprovalEvidence.model_validate(
                {**evidence.model_dump(mode="python"), **changed}
            )


def test_low_cost_evidence_forbids_review(final_ctx):
    low = submit_low_cost(final_ctx, "RL-OPTION-TRANSFER")
    value = ProposalApprovalEvidence(
        selection=low.selection, review=None, review_revision=None
    )
    assert value.review is None

@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("submitter", "identity_source", "fixture"),
        ("submitter", "effective_roles", ("material_planner",)),
        ("submitter", "object_id", "not-a-uuid"),
        ("reviewer", "persona_id", "RL-PERSONA-ALEX"),
        ("reviewer", "source_id", "RL-ENTRA-ALEX"),
        ("reviewer", "effective_roles", ("finance_approver", "extra")),
        ("reviewer", "tenant_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("reviewer", "object_id", "22222222-2222-4222-8222-222222222222"),
    ),
)
def test_evidence_requires_pure_exact_actor_shapes(final_ctx, target, field, value):
    approved = submit_and_approve(final_ctx)
    selection = approved.selection
    review = approved.resolution.review
    assert review.reviewed_by is not None
    if target == "submitter":
        actor = selection.submitted_by.model_copy(update={field: value})
        selection = selection.model_copy(update={"submitted_by": actor})
    else:
        actor = review.reviewed_by.model_copy(update={field: value})
        review = review.model_copy(update={"reviewed_by": actor})
    with pytest.raises(ValidationError):
        ProposalApprovalEvidence(
            selection=selection, review=review,
            review_revision=approved.resolution.review_revision,
        )


def test_frozen_legacy_decision_json_is_byte_identical():
    fixture = json.loads(Path("tests/finance/fixtures/legacy-policy.json").read_text())
    decision = Decision.model_validate_json(fixture["decision"])
    assert decision.proposal_approval is None
    assert serialize_model(decision) == fixture["decision"]
    assert "proposal_approval" not in json.loads(serialize_model(decision))
```

Run:

```bash
.venv/bin/python -m pytest tests/finance/test_finance_final_decision.py tests/finance/test_workflow_policy.py -q -m 'not fabric_live' -o addopts=''
```

Expected RED: collection fails on missing `ProposalApprovalEvidence`/Decision field, not fixture setup.

- [ ] **Step 2: Implement immutable evidence and additive Decision JSON**

Create `data/domain/finance_decisions.py`:

```python
from decimal import Decimal
from uuid import UUID
from pydantic import Field, StrictInt, model_validator
from data.domain.common import FrozenModel
from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.finance import FinanceReview, FinanceReviewStatus
from data.domain.proposals import ProposalSelection

def _require_identity(
    actor: IdentitySnapshot, *, persona_id: str, source_id: str,
    roles: tuple[str, ...],
) -> tuple[UUID, UUID]:
    if (
        actor.persona_id != persona_id
        or actor.source_id != source_id
        or actor.identity_source is not IdentitySource.ENTRA
        or actor.effective_roles != roles
    ):
        raise ValueError("Proposal evidence contains an invalid identity shape")
    try:
        return UUID(actor.tenant_id or ""), UUID(actor.object_id or "")
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("Proposal evidence identity requires tenant/object UUIDs") from error

class ProposalApprovalEvidence(FrozenModel):
    selection: ProposalSelection
    review: FinanceReview | None = None
    review_revision: StrictInt | None = Field(default=None, gt=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "ProposalApprovalEvidence":
        submitter_tenant, submitter_object = _require_identity(
            self.selection.submitted_by,
            persona_id="RL-PERSONA-ALEX", source_id="RL-ENTRA-ALEX",
            roles=("material_planner", "response_approver"),
        )
        needs_finance = self.selection.proposal.response_cost > Decimal("20000.00")
        if needs_finance != (self.review is not None):
            raise ValueError("Finance review presence conflicts with proposal cost")
        if self.review is None:
            if self.review_revision is not None or self.selection.finance_review_id is not None:
                raise ValueError("Low-cost proposal cannot contain Finance review evidence")
            return self
        review = self.review
        if (
            self.review_revision is None
            or review.status is not FinanceReviewStatus.APPROVED
            or self.selection.finance_review_id != review.review_id
            or review.proposal != self.selection.proposal
            or review.submitted_by != self.selection.submitted_by
            or review.submitted_at != self.selection.submitted_at
            or review.reviewed_by is None or review.reviewed_at is None
        ):
            raise ValueError("Proposal requires an exact approved Finance revision")
        reviewer_tenant, reviewer_object = _require_identity(
            review.reviewed_by,
            persona_id="RL-PERSONA-TAYLOR", source_id="RL-ENTRA-TAYLOR",
            roles=("finance_approver",),
        )
        if reviewer_tenant != submitter_tenant:
            raise ValueError("Finance reviewer must share the submitter tenant")
        if reviewer_object == submitter_object:
            raise ValueError("Submitter and reviewer must differ")
        return self
```

In `data/domain/decisions.py`, import `UUID`, `WorkflowVersion`, `SerializerFunctionWrapHandler`, and `model_serializer`; add `proposal_approval: Any | None = None` after existing satisfaction material. Add:

```python
    @field_validator("proposal_approval", mode="before")
    @classmethod
    def decode_proposal_approval(cls, value: Any) -> Any:
        if value is None:
            return None
        from .finance_decisions import ProposalApprovalEvidence
        return ProposalApprovalEvidence.model_validate(value)

    @model_serializer(mode="wrap")
    def omit_absent_proposal_approval(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload = handler(self)
        if self.proposal_approval is None:
            payload.pop("proposal_approval", None)
        return payload
```

Make three exact edits to `validate_immutable_shape`; do not add a second rejected branch or an earlier return. First insert this as the first statement in the existing method, before its current rejected branch:

```python
        independent = self.approval_policy_version == WorkflowVersion.INDEPENDENT_FINANCE.value
```

Second, add this operand inside the existing rejected Decision `if (` condition, immediately after `self.approval_satisfactions` and before the rejection-reason checks:

```python
                or self.proposal_approval is not None
```

The existing rejected shape checks and their existing `return self` remain exactly where they are. Third, insert the following after the existing approved satisfaction loop has validated every satisfaction and before the method's final `return self`:

```python
        if independent != (self.proposal_approval is not None):
            raise ValueError("Decision policy conflicts with proposal evidence")
        if self.proposal_approval is not None:
            evidence = self.proposal_approval
            selection = evidence.selection
            if (
                selection.proposal.case_id != self.case_id
                or selection.proposal.analysis_id != self.analysis_id
                or selection.proposal.analysis_material_hash != self.analysis_material_hash
                or selection.proposal.option_id != self.selected_option_id
                or self.selected_option is None or self.selected_option.predicted is None
                or selection.proposal.response_cost != self.selected_option.predicted.response_cost
                or self.decided_at < selection.submitted_at
            ):
                raise ValueError("Decision conflicts with proposal evidence")
            try:
                final_actor = (UUID(self.actor.tenant_id or ""), UUID(self.actor.object_id or ""))
                submitter = (UUID(selection.submitted_by.tenant_id or ""), UUID(selection.submitted_by.object_id or ""))
            except (ValueError, TypeError, AttributeError) as error:
                raise ValueError("Decision requires exact Alex identity") from error
            if final_actor != submitter:
                raise ValueError("Final Alex differs from proposal submitter")
            if evidence.review is not None:
                reviewed_at = evidence.review.reviewed_at
                if reviewed_at is None or self.decided_at < reviewed_at:
                    raise ValueError("Decision time precedes Finance approval")
            if any(item.role == "finance_approver" for item in self.approval_satisfactions):
                raise ValueError("Independent Decision cannot use standing Finance satisfaction")
```

Add keyword-only `proposal_approval: Any | None = None` to `Decision.from_command` and pass it as `proposal_approval=proposal_approval` in the existing `cls` constructor. Existing calls remain source-compatible. All negative tests must rebuild through `Decision.model_validate`, not unchecked `model_copy(update=...)`.

- [ ] **Step 3: Write RED tests for independent policy and legacy isolation**

```python
def test_independent_policy_excludes_only_finance_standing(final_ctx):
    inputs = approved_policy_inputs(final_ctx)
    satisfactions = DecisionPolicy().authorize_independent_and_materialize(**inputs)
    assert {item.role for item in satisfactions} == {"material_planner"}

def test_independent_policy_keeps_nonfinance_prerequisites(final_ctx):
    inputs = quality_option_inputs_without_satisfaction(final_ctx)
    with pytest.raises(DecisionPolicyViolation, match="quality_approver"):
        DecisionPolicy().authorize_independent_and_materialize(**inputs)

@pytest.mark.parametrize("kind", (DecisionKind.APPROVED, DecisionKind.REJECTED))
def test_legacy_service_rejects_independent_case_before_write(final_ctx, kind):
    if kind is DecisionKind.APPROVED:
        final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    before = final_counts_and_projection(final_ctx)
    with pytest.raises(DecisionPolicyViolation, match="INDEPENDENT_FINANCE_REQUIRED"):
        DecisionService(final_ctx.store.uow_factory).record(
            legacy_command_from_current(final_ctx, kind), final_ctx.alex
        )
    assert final_counts_and_projection(final_ctx) == before

def test_legacy_service_rejects_independent_receipt_replay(final_ctx):
    decision = finalize_approved(final_ctx)
    command = record_command_matching(decision)
    with pytest.raises(DecisionPolicyViolation, match="INDEPENDENT_FINANCE_REQUIRED"):
        DecisionService(final_ctx.store.uow_factory).record(command, final_ctx.alex)
```

Expected RED: missing policy method and legacy service accepts independent cases/receipts.

- [ ] **Step 4: Implement the named policy path and legacy boundary**

Change `_revalidate_existing_satisfactions` to accept `excluded_roles: frozenset[str] = frozenset()`. Filter those roles before the initial `any(not item.satisfied...)` check and subtract them from `required_roles`; leave target, StandingAuthorization, persona, cardinality, and sorted return checks unchanged. The legacy default remains identical.

```python
    def authorize_independent_and_materialize(
        self, command, actor, case, projection, analysis,
        proposal_approval: ProposalApprovalEvidence | None,
    ) -> tuple[ApprovalSatisfaction, ...]:
        self._authorize_actor(command, actor)
        self._require_current_analysis(command, case, projection, analysis)
        if command.kind is DecisionKind.REJECTED:
            if proposal_approval is not None:
                raise DecisionPolicyViolation("Rejection cannot contain proposal evidence")
            return ()
        if proposal_approval is None:
            raise DecisionPolicyViolation("Approval requires proposal evidence")
        option = self._selected_option(command, analysis)
        if proposal_approval.selection.proposal.option_id != option.option_id:
            raise DecisionPolicyViolation("Option differs from current proposal")
        existing = self._revalidate_existing_satisfactions(
            case=case, analysis=analysis, option=option,
            excluded_roles=frozenset({"finance_approver"}),
        )
        material = self._alex_material_planner_satisfaction(
            actor=actor, case=case, analysis=analysis, option=option
        )
        return tuple(sorted((*existing, material), key=lambda item: item.role))
```

In `DecisionService._return_existing`, reject an existing Decision whose `approval_policy_version == WorkflowVersion.INDEPENDENT_FINANCE.value` before old fingerprint comparison. In `record`, after loading the case and before materializing either Decision kind, reject `case.effective_workflow_version is WorkflowVersion.INDEPENDENT_FINANCE`. Both raise `DecisionPolicyViolation("INDEPENDENT_FINANCE_REQUIRED: use FinanceDecisionService")`. Do not change the legacy fingerprint.

- [ ] **Step 5: Write RED tests for atomic withdrawal**

```python
def test_withdraw_clears_selection_supersedes_review_and_preserves_analysis(final_ctx):
    submitted = final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    before = current(final_ctx)
    with final_ctx.store.uow_factory() as uow:
        returned = uow.proposals.withdraw_current(
            final_ctx.case.case_id, expected=before.token, now=FINALIZED_AT,
            operation_id="RL-DECISION-WITHDRAW-1"
        )
        uow.commit()
    after = current(final_ctx)
    assert returned == after.token
    assert after.token.generation == before.token.generation + 1
    assert after.token.analysis_id == before.token.analysis_id
    assert after.token.selection_id is None
    with final_ctx.store.uow_factory() as uow:
        review, revision = uow.finance_reviews.get_latest(submitted.review.review_id)
    assert revision == 2 and review.status is FinanceReviewStatus.SUPERSEDED

def test_low_cost_withdraw_rejects_backward_time(final_ctx):
    low = submit_low_cost(final_ctx, "RL-OPTION-TRANSFER")
    before = final_counts_and_projection(final_ctx)
    with pytest.raises(ValueError, match="precede proposal submission"):
        with final_ctx.store.uow_factory() as uow:
            uow.proposals.withdraw_current(
                final_ctx.case.case_id, expected=current(final_ctx).token,
                now=low.selection.submitted_at - timedelta(seconds=1),
                operation_id="RL-DECISION-WITHDRAW-BACKWARD"
            )
    assert final_counts_and_projection(final_ctx) == before

@pytest.mark.parametrize("bad", ("naive", "stale", "legacy"))
def test_withdraw_rejects_invalid_guard_inputs(final_ctx, bad):
    assert_withdraw_guard_failure_and_no_writes(final_ctx, bad)
```

Expected RED: `ProposalStore` lacks `withdraw_current`.

- [ ] **Step 6: Implement one-CAS withdrawal on the existing connection**

Add to `ProposalStore` and `SqlAlchemyProposalRepository`:

```python
    def withdraw_current(
        self, case_id: str, *, expected: ProposalToken,
        now: datetime, operation_id: str,
    ) -> ProposalToken:
        case = self._store._stored_case(self._connection, case_id)
        if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
            raise PersistenceIntegrityError("Case does not use independent Finance workflow")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Withdrawal time must be timezone-aware")
        if not operation_id.strip():
            raise ValueError("Withdrawal operation_id must be nonblank")
        state = self.get_state(case_id)
        if state.token != expected:
            raise StaleProposal("Case analysis or proposal changed")
        if state.selection is not None and now < state.selection.submitted_at:
            raise ValueError("Withdrawal cannot precede proposal submission")
        _cas_projection(self._connection, case_id=case_id, expected=expected,
            values={"current_selection_id": None, "updated_at": now})
        if state.review is not None:
            superseded = supersede_finance_review(review=state.review, now=now)
            material = {
                "operation": "decision-withdraw", "decision_id": operation_id,
                "prior_review_id": state.review.review_id,
                "prior_revision": state.review_revision,
                "superseded_at": now.isoformat(),
            }
            fingerprint = hashlib.sha256(json.dumps(
                material, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
            self._finance.append(
                superseded, expected_revision=state.review_revision,
                idempotency_key=f"decision-withdraw:{operation_id}",
                request_fingerprint=fingerprint,
            )
        return expected.model_copy(
            update={"generation": expected.generation + 1, "selection_id": None}
        )
```

No internal commit, guard call, separate connection, or second proposal CAS.

- [ ] **Step 7: Write RED acceptance tests for the finalization service**

The focused file starts with this import block and the following concrete fixture/helpers:

```python
import json
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from typing import Never, cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from data.domain import CasePurpose, RuntimeMode
from data.domain.analysis import AnalysisResponseOptionMaterial, AnalysisVersion
from data.domain.cases import WorkflowVersion
from data.domain.decisions import CorpusScope, Decision, DecisionKind, IdentitySnapshot, RecordDecisionCommand, StandingAuthorization
from data.domain.evidence import IdentitySource
from data.domain.execution import ActionPlanningRequested
from data.domain.finance import FinanceReviewStatus
from data.domain.finance_decisions import ProposalApprovalEvidence
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionPolicy, DecisionPolicyViolation, DecisionService
from services.finance.contracts import FinalizeProposalCommand, ResolveFinanceCommand, SubmitProposalCommand
from services.finance.decisions import FinanceDecisionService, FinanceFinalizationConflict, FinanceFinalizationInvalid
from services.finance.identity import BoundFinanceActors, FinancePermissionDenied
from services.finance.service import FinanceCommandConflict, FinanceService
from services.persistence.ports import UnitOfWork
from services.persistence.finance_reviews import FinanceReviewRevisionConflict
import services.persistence.proposals as proposals_module
from services.persistence.proposals import StaleProposal
from services.persistence.sqlite import SqliteStore, build_sqlite_engine, sqlite_store
from services.persistence.store import PersistenceIntegrityError, serialize_model
from services.persistence.tables import analysis_versions, approval_satisfactions, case_projection, case_proposal_selections, decisions, outbox_events

START = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
SUBMITTED = datetime.fromisoformat("2026-09-01T14:02:00+00:00")
REVIEWED = SUBMITTED + timedelta(minutes=1)
FINALIZED_AT = REVIEWED + timedelta(minutes=1)

@pytest.fixture
def final_ctx(tmp_path):
    tenant = "11111111-1111-4111-8111-111111111111"
    alex_id = "22222222-2222-4222-8222-222222222222"
    taylor_id = "33333333-3333-4333-8333-333333333333"
    actors = BoundFinanceActors(
        tenant_id=UUID(tenant), alex_object_id=UUID(alex_id),
        taylor_object_id=UUID(taylor_id),
    )
    alex = IdentitySnapshot(
        persona_id="RL-PERSONA-ALEX", source_id="RL-ENTRA-ALEX",
        identity_source=IdentitySource.ENTRA, tenant_id=tenant,
        object_id=alex_id,
        effective_roles=("material_planner", "response_approver"),
    )
    taylor = IdentitySnapshot(
        persona_id="RL-PERSONA-TAYLOR", source_id="RL-ENTRA-TAYLOR",
        identity_source=IdentitySource.ENTRA, tenant_id=tenant,
        object_id=taylor_id, effective_roles=("finance_approver",),
    )
    store = sqlite_store(f"sqlite:///{tmp_path / 'finance-final.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-FINANCE-FINAL", purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    analysis = analyze_case(AnalyzeCaseCommand(
        analysis_id="RL-ANALYSIS-FINANCE-FINAL", case=case,
        corpus=CorpusScope.DEMO_CORPUS, operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(
            snapshot, analysis_id="RL-ANALYSIS-FINANCE-FINAL", retrieved_at=START
        ),
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=START, created_at=START,
        calculation_version="rl001-options-v1",
    ))
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    finance_times = iter((SUBMITTED, REVIEWED, FINALIZED_AT + timedelta(minutes=1)))
    finance = FinanceService(
        cast(Callable[[], UnitOfWork], store.uow_factory), actors=actors,
        clock=lambda: next(finance_times),
    )
    finalizer = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], store.uow_factory), actors=actors,
        clock=lambda: FINALIZED_AT,
    )
    yield SimpleNamespace(
        store=store, case=case, snapshot=snapshot, analysis=analysis,
        actors=actors, alex=alex, taylor=taylor,
        finance=finance, finalizer=finalizer,
    )
    store.engine.dispose()

def current(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)

def submission(ctx, option="RL-OPTION-COMBINED", key="submit-1"):
    return SubmitProposalCommand(
        case_id=ctx.case.case_id, option_id=option,
        expected=current(ctx).token, idempotency_key=key,
    )

def resolution(ctx, *, approved=False, reason="Budget 10000", key="resolve-1"):
    state = current(ctx)
    assert state.review is not None and state.review_revision is not None
    return ResolveFinanceCommand(
        review_id=state.review.review_id, expected=state.token,
        expected_review_revision=state.review_revision, approved=approved,
        reason=reason, idempotency_key=key,
    )

def finalize_command(ctx, kind, *, key="final-1", reason=None):
    return FinalizeProposalCommand(
        case_id=ctx.case.case_id, expected=current(ctx).token, kind=kind,
        idempotency_key=key, rejection_reason=reason,
    )

def submit_and_approve(ctx):
    submitted = ctx.finance.submit(submission(ctx), ctx.alex)
    resolved = ctx.finance.resolve(
        resolution(ctx, approved=True, reason=None), ctx.taylor
    )
    return SimpleNamespace(
        selection=submitted.selection, pending=submitted.review,
        resolution=resolved,
    )

def submit_low_cost(ctx, option):
    return ctx.finance.submit(submission(ctx, option=option), ctx.alex)

def final_row_counts(ctx):
    with ctx.store.engine.connect() as connection:
        return tuple(connection.scalar(select(func.count()).select_from(table))
            for table in (decisions, approval_satisfactions, outbox_events))

def final_counts_and_projection(ctx):
    with ctx.store.uow_factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
    return current(ctx), final_row_counts(ctx), projection

def forbidden_uow() -> Never:
    raise AssertionError("unauthorized/replay request opened a UoW")

def no_clock():
    raise AssertionError("replay read the clock")

def wrong_object_alex(ctx):
    return ctx.alex.model_copy(
        update={"object_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    )

def extra_role_alex(ctx):
    return ctx.alex.model_copy(update={
        "effective_roles": (*ctx.alex.effective_roles, "finance_approver")
    })

def equivalent_refreshed_alex(ctx):
    return ctx.alex.model_copy(update={
        "tenant_id": UUID(ctx.alex.tenant_id).hex,
        "object_id": UUID(ctx.alex.object_id).hex,
        "display_name": "Refreshed Alex",
        "user_principal_name": "refreshed@example.invalid",
    })

def persist_final_decision(ctx):
    submit_and_approve(ctx)
    command = finalize_command(ctx, DecisionKind.APPROVED)
    return command, ctx.finalizer.finalize(command, ctx.alex)

def finalize_approved(ctx):
    submit_and_approve(ctx)
    return ctx.finalizer.finalize(
        finalize_command(ctx, DecisionKind.APPROVED), ctx.alex
    )

def reject_current_analysis(ctx, *, key="reject-1"):
    return ctx.finalizer.finalize(
        finalize_command(ctx, DecisionKind.REJECTED, key=key, reason="reject"),
        ctx.alex,
    )

def count_events(ctx, decision_id):
    with ctx.store.engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(outbox_events).where(
            outbox_events.c.decision_id == decision_id
        ))

def approved_policy_inputs(ctx):
    approved = submit_and_approve(ctx)
    state = current(ctx)
    with ctx.store.uow_factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
        analysis = uow.cases.get_analysis(ctx.analysis.analysis_id)
    evidence = ProposalApprovalEvidence(
        selection=approved.selection, review=approved.resolution.review,
        review_revision=approved.resolution.review_revision,
    )
    command = RecordDecisionCommand(
        case_id=ctx.case.case_id, analysis_id=analysis.analysis_id,
        selected_option_id=state.selection.proposal.option_id,
        kind=DecisionKind.APPROVED, idempotency_key="policy-check",
    )
    return dict(command=command, actor=ctx.alex, case=ctx.case,
        projection=projection, analysis=analysis, proposal_approval=evidence)

def quality_option_inputs_without_satisfaction(ctx):
    values = approved_policy_inputs(ctx)
    analysis = values["analysis"]
    option = next(item for item in analysis.response_options
        if item.option_id == values["command"].selected_option_id)
    changed = option.model_copy(update={
        "prerequisite_roles": (*option.prerequisite_roles, "quality_approver")
    })
    material_options = tuple(
        AnalysisResponseOptionMaterial.from_option(changed)
        if item.option_id == changed.option_id else item
        for item in analysis.material.response_options
    )
    changed_material = analysis.material.model_copy(update={
        "response_options": material_options
    })
    values["analysis"] = analysis.model_copy(update={
        "response_options": tuple(changed if item.option_id == changed.option_id else item
            for item in analysis.response_options),
        "material": changed_material,
        "approval_satisfactions": tuple(item for item in analysis.approval_satisfactions
            if item.role != "quality_approver"),
    })
    return values

def legacy_command_from_current(ctx, kind):
    state = current(ctx)
    return RecordDecisionCommand(
        case_id=ctx.case.case_id, analysis_id=ctx.analysis.analysis_id,
        selected_option_id=(state.selection.proposal.option_id
            if kind is DecisionKind.APPROVED else None),
        kind=kind, idempotency_key=f"legacy-{kind.value}",
        rejection_reason="reject" if kind is DecisionKind.REJECTED else None,
    )

def record_command_matching(decision):
    return RecordDecisionCommand(
        case_id=decision.case_id, analysis_id=decision.analysis_id,
        selected_option_id=decision.selected_option_id, kind=decision.kind,
        idempotency_key=decision.idempotency_key,
        rejection_reason=decision.rejection_reason,
    )

def arrange_review_state(ctx, state):
    first = ctx.finance.submit(submission(ctx), ctx.alex)
    if state == "pending":
        return first
    ctx.finance.resolve(resolution(ctx, approved=False), ctx.taylor)
    if state == "rejected":
        return first
    replacement = ctx.finance.submit(submission(ctx, key="superseding"), ctx.alex)
    with ctx.store.engine.begin() as connection:
        connection.execute(update(case_projection).where(
            case_projection.c.case_id == ctx.case.case_id
        ).values(current_selection_id=first.selection.selection_id))
    return replacement

def assert_finalize_fails_without_writes(ctx, kind):
    before = final_counts_and_projection(ctx)
    with pytest.raises((FinanceFinalizationInvalid, StaleProposal, PersistenceIntegrityError)):
        ctx.finalizer.finalize(finalize_command(ctx, kind), ctx.alex)
    assert final_counts_and_projection(ctx) == before

def arrange_rejection_state(ctx, state):
    if state == "none":
        return
    ctx.finance.submit(submission(ctx), ctx.alex)
    if state == "approved":
        ctx.finance.resolve(resolution(ctx, approved=True, reason=None), ctx.taylor)

def arrange_valid_state_for_kind(ctx, kind):
    if kind is DecisionKind.APPROVED:
        submit_and_approve(ctx)

def seed_foreign_owned_current_selection(ctx, selection_state):
    other_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    other = ctx.alex.model_copy(update={"object_id": other_id})
    actors = BoundFinanceActors(
        tenant_id=ctx.actors.tenant_id, alex_object_id=UUID(other_id),
        taylor_object_id=ctx.actors.taylor_object_id,
    )
    service = FinanceService(
        cast(Callable[[], UnitOfWork], ctx.store.uow_factory), actors=actors,
        clock=lambda: SUBMITTED,
    )
    option = "RL-OPTION-COMBINED" if selection_state == "pending" else "RL-OPTION-TRANSFER"
    service.submit(submission(ctx, option=option, key=f"foreign-{selection_state}"), other)

def persist_later_analysis_and_selection(ctx):
    analysis_id = "RL-ANALYSIS-FINANCE-FINAL-LATER"
    later = analyze_case(AnalyzeCaseCommand(
        analysis_id=analysis_id, case=ctx.case, corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=ctx.snapshot,
        evidence_items=build_rl001_evidence(
            ctx.snapshot, analysis_id=analysis_id, retrieved_at=FINALIZED_AT
        ),
        analysis_started_at=FINALIZED_AT, created_at=FINALIZED_AT,
        calculation_version="rl001-options-v1",
    ))
    ctx.store.save_analysis(later)
    ctx.finance.submit(submission(ctx, key="later-selection"), ctx.alex)

def point_case_at_persisted_rejected_decision(ctx):
    state = current(ctx)
    with ctx.store.uow_factory() as uow:
        projection = uow.cases.get_projection(ctx.case.case_id)
        analysis = uow.cases.get_analysis(state.token.analysis_id)
        command = RecordDecisionCommand(
            case_id=ctx.case.case_id, analysis_id=analysis.analysis_id,
            selected_option_id=None, kind=DecisionKind.REJECTED,
            idempotency_key="test-rejected-pointer", rejection_reason="test pointer",
        )
        satisfactions = DecisionPolicy().authorize_independent_and_materialize(
            command, ctx.alex, ctx.case, projection, analysis, None
        )
        rejected = Decision.from_command(command, ctx.alex, analysis, satisfactions,
            request_fingerprint="0" * 64, decided_at=FINALIZED_AT + timedelta(minutes=1))
        uow.decisions.insert(rejected)
        uow.cases.mark_rejected(ctx.case.case_id, rejected.decision_id)
        uow.commit()

def assert_withdraw_guard_failure_and_no_writes(ctx, bad):
    if bad != "legacy":
        ctx.finance.submit(submission(ctx), ctx.alex)
    before = final_counts_and_projection(ctx)
    expected = current(ctx).token
    now = FINALIZED_AT
    case_id = ctx.case.case_id
    if bad == "naive":
        now = datetime(2026, 9, 1)
    elif bad == "stale":
        expected = expected.model_copy(update={"generation": expected.generation - 1})
    else:
        legacy, snapshot = instantiate_rl001(
            case_id="RL-CASE-WITHDRAW-LEGACY", purpose=CasePurpose.AUTOMATED_TEST,
            runtime_mode=RuntimeMode.FALLBACK, workflow_version=WorkflowVersion.LEGACY
        )
        ctx.store.create_case(legacy, snapshot)
        case_id = legacy.case_id
        with ctx.store.uow_factory() as uow:
            expected = uow.proposals.get_state(case_id).token
    with pytest.raises((ValueError, StaleProposal, PersistenceIntegrityError)):
        with ctx.store.uow_factory() as uow:
            uow.proposals.withdraw_current(case_id, expected=expected, now=now,
                operation_id=f"withdraw-{bad}")
            uow.commit()
    assert final_counts_and_projection(ctx) == before

def rebuild_and_persist_expedite_cost(base_ctx, tmp_path, cost):
    label = str(cost).replace(".", "-")
    case, snapshot = instantiate_rl001(
        case_id=f"RL-CASE-FINAL-COST-{label}",
        purpose=CasePurpose.AUTOMATED_TEST, runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE,
    )
    assert snapshot.alpha_expedite is not None
    snapshot = snapshot.model_copy(update={"alpha_expedite":
        snapshot.alpha_expedite.model_copy(update={
            "quantity": 1, "incremental_cost_per_unit": cost
        })})
    analysis_id = f"RL-ANALYSIS-FINAL-COST-{label}"
    analysis = analyze_case(AnalyzeCaseCommand(
        analysis_id=analysis_id, case=case, corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(
            snapshot, analysis_id=analysis_id, retrieved_at=START
        ),
        analysis_started_at=START, created_at=START,
        calculation_version="rl001-options-v1",
    ))
    store = sqlite_store(f"sqlite:///{tmp_path / f'final-cost-{label}.db'}")
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    times = iter((SUBMITTED, REVIEWED))
    finance = FinanceService(cast(Callable[[], UnitOfWork], store.uow_factory),
        actors=base_ctx.actors, clock=lambda: next(times))
    finalizer = FinanceDecisionService(
        cast(Callable[[], UnitOfWork], store.uow_factory),
        actors=base_ctx.actors, clock=lambda: FINALIZED_AT)
    return SimpleNamespace(store=store, case=case, snapshot=snapshot,
        analysis=analysis, actors=base_ctx.actors, alex=base_ctx.alex,
        taylor=base_ctx.taylor, finance=finance, finalizer=finalizer,
        option_id="RL-OPTION-EXPEDITE")
```

The threshold test closes each returned cost context's engine in a `finally` block; it never mutates the primary fixture snapshot.

The focused file must contain these named tests with real persisted services:

```python
def test_high_cost_approval_records_exact_evidence_one_decision_and_event(final_ctx):
    approved = submit_and_approve(final_ctx)
    before_generation = current(final_ctx).token.generation
    decision = final_ctx.finalizer.finalize(
        finalize_command(final_ctx, DecisionKind.APPROVED), final_ctx.alex
    )
    assert decision.proposal_approval.selection == approved.selection
    assert decision.proposal_approval.review == approved.resolution.review
    assert decision.proposal_approval.review_revision == 2
    assert decision.proposal_approval.review.reviewed_by == final_ctx.taylor
    assert {item.role for item in decision.approval_satisfactions} == {"material_planner"}
    assert current(final_ctx).token.generation == before_generation + 1
    assert final_row_counts(final_ctx) == (1, 1, 1)

@pytest.mark.parametrize("state", ("pending", "rejected", "superseded"))
def test_high_cost_requires_current_approved_review(final_ctx, state):
    arrange_review_state(final_ctx, state)
    assert_finalize_fails_without_writes(final_ctx, DecisionKind.APPROVED)

@pytest.mark.parametrize("option", ("RL-OPTION-TRANSFER", "RL-OPTION-RESEQUENCE"))
def test_low_cost_approval_has_selection_but_no_finance(final_ctx, option):
    selected = submit_low_cost(final_ctx, option)
    decision = final_ctx.finalizer.finalize(
        finalize_command(final_ctx, DecisionKind.APPROVED), final_ctx.alex
    )
    assert decision.proposal_approval.selection == selected.selection
    assert decision.proposal_approval.review is None
    assert final_row_counts(final_ctx) == (1, 1, 1)

@pytest.mark.parametrize(
    ("cost", "needs_review"), (("20000.00", False), ("20000.01", True))
)
def test_finalization_uses_exact_saved_cost_threshold(
    final_ctx, tmp_path, cost, needs_review
):
    rebuilt = rebuild_and_persist_expedite_cost(
        final_ctx, tmp_path, Decimal(cost)
    )
    try:
        selected = rebuilt.finance.submit(
            submission(rebuilt, option=rebuilt.option_id), rebuilt.alex
        )
        if needs_review:
            rebuilt.finance.resolve(
                resolution(rebuilt, approved=True, reason=None), rebuilt.taylor
            )
        decision = rebuilt.finalizer.finalize(
            finalize_command(rebuilt, DecisionKind.APPROVED), rebuilt.alex
        )
        assert selected.selection.proposal.response_cost == Decimal(cost)
        assert decision.selected_option.predicted.response_cost == Decimal(cost)
        assert (decision.proposal_approval.review is not None) is needs_review
    finally:
        rebuilt.store.engine.dispose()

@pytest.mark.parametrize("state", ("none", "pending", "approved"))
def test_alex_rejection_withdraws_optional_selection_atomically(final_ctx, state):
    arrange_rejection_state(final_ctx, state)
    before = current(final_ctx)
    decision = final_ctx.finalizer.finalize(
        finalize_command(final_ctx, DecisionKind.REJECTED, reason="reject analysis"),
        final_ctx.alex,
    )
    after = current(final_ctx)
    assert decision.proposal_approval is None
    assert after.token.selection_id is None
    assert after.token.analysis_id == before.token.analysis_id
    assert after.token.generation == before.token.generation + 1
    assert final_row_counts(final_ctx) == (1, 0, 0)
    assert final_ctx.finance.list_pending(final_ctx.taylor) == ()

def test_withdrawal_makes_old_taylor_command_stale_and_resubmit_gets_new_review(final_ctx):
    first = final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    old = resolution(final_ctx, approved=True, reason=None)
    reject_current_analysis(final_ctx)
    with pytest.raises(StaleProposal):
        final_ctx.finance.resolve(old, final_ctx.taylor)
    second = final_ctx.finance.submit(submission(final_ctx, key="second"), final_ctx.alex)
    assert second.selection.selection_id != first.selection.selection_id
    assert second.review.review_id != first.review.review_id

def test_authorization_precedes_initial_and_committed_replay_uow(final_ctx):
    command, original = persist_final_decision(final_ctx)
    denied = FinanceDecisionService(forbidden_uow, actors=final_ctx.actors, clock=no_clock)
    for actor in (final_ctx.taylor, wrong_object_alex(final_ctx), extra_role_alex(final_ctx)):
        with pytest.raises(FinancePermissionDenied):
            denied.finalize(command, actor)
    assert final_ctx.finalizer.finalize(command, equivalent_refreshed_alex(final_ctx)) == original

@pytest.mark.parametrize("selection_state", ("pending", "low_cost"))
def test_rejection_denies_foreign_current_selection_owner_before_mutation(
    final_ctx, selection_state
):
    seed_foreign_owned_current_selection(final_ctx, selection_state)
    before = final_counts_and_projection(final_ctx)
    with pytest.raises(FinancePermissionDenied):
        final_ctx.finalizer.finalize(
            finalize_command(
                final_ctx, DecisionKind.REJECTED,
                key=f"foreign-{selection_state}", reason="reject"
            ),
            final_ctx.alex,
        )
    assert final_counts_and_projection(final_ctx) == before

def test_replay_returns_original_after_later_selection_and_analysis(final_ctx):
    command, original = persist_final_decision(final_ctx)
    persist_later_analysis_and_selection(final_ctx)
    replay = FinanceDecisionService(
        final_ctx.store.uow_factory, actors=final_ctx.actors, clock=no_clock
    ).finalize(command, final_ctx.alex)
    assert replay == original

def test_approved_selection_duplicate_scan_ignores_rejected_current_pointer(final_ctx):
    approved = finalize_approved(final_ctx)
    point_case_at_persisted_rejected_decision(final_ctx)
    with pytest.raises(FinanceFinalizationConflict, match="already finalized"):
        final_ctx.finalizer.finalize(
            finalize_command(final_ctx, DecisionKind.APPROVED, key="fresh"), final_ctx.alex
        )
    assert count_events(final_ctx, approved.decision_id) == 1

def test_finalized_selection_cannot_be_withdrawn(final_ctx):
    finalize_approved(final_ctx)
    with pytest.raises(FinanceFinalizationConflict, match="active execution"):
        reject_current_analysis(final_ctx, key="withdraw-finalized")

@pytest.mark.parametrize("kind", (DecisionKind.APPROVED, DecisionKind.REJECTED))
def test_naive_clock_rejected_for_both_kinds(final_ctx, kind):
    arrange_valid_state_for_kind(final_ctx, kind)
    service = FinanceDecisionService(final_ctx.store.uow_factory,
        actors=final_ctx.actors, clock=lambda: datetime(2026, 9, 1))
    reason = "reject" if kind is DecisionKind.REJECTED else None
    with pytest.raises(FinanceFinalizationInvalid, match="timezone-aware"):
        service.finalize(finalize_command(final_ctx, kind, reason=reason), final_ctx.alex)
```

Add these concrete conflict/rollback/read tests:

```python
def test_same_key_changed_token_kind_or_reason_conflicts(final_ctx):
    submit_and_approve(final_ctx)
    command = finalize_command(final_ctx, DecisionKind.APPROVED)
    final_ctx.finalizer.finalize(command, final_ctx.alex)
    changed_token = command.model_copy(update={"expected":
        command.expected.model_copy(update={"generation": command.expected.generation + 1})})
    changed_kind = command.model_copy(update={
        "kind": DecisionKind.REJECTED, "rejection_reason": "changed"
    })
    for changed in (changed_token, changed_kind):
        with pytest.raises(FinanceFinalizationConflict):
            final_ctx.finalizer.finalize(changed, final_ctx.alex)

def test_rejection_same_key_changed_reason_conflicts(final_ctx):
    original = finalize_command(
        final_ctx, DecisionKind.REJECTED, key="reject-key", reason="first"
    )
    final_ctx.finalizer.finalize(original, final_ctx.alex)
    changed = original.model_copy(update={"rejection_reason": "different"})
    with pytest.raises(FinanceFinalizationConflict):
        final_ctx.finalizer.finalize(changed, final_ctx.alex)

def test_fresh_key_same_selection_conflicts(final_ctx):
    submit_and_approve(final_ctx)
    final_ctx.finalizer.finalize(
        finalize_command(final_ctx, DecisionKind.APPROVED), final_ctx.alex
    )
    fresh = FinalizeProposalCommand(
        case_id=final_ctx.case.case_id, expected=current(final_ctx).token,
        kind=DecisionKind.APPROVED, idempotency_key="fresh-key"
    )
    with pytest.raises(FinanceFinalizationConflict, match="already finalized"):
        final_ctx.finalizer.finalize(fresh, final_ctx.alex)

@pytest.mark.parametrize(
    ("kind", "seam"),
    ((DecisionKind.APPROVED, "decision"),
     (DecisionKind.APPROVED, "outbox"),
     (DecisionKind.REJECTED, "decision")),
)
def test_decision_or_outbox_failure_rolls_back_everything(final_ctx, kind, seam):
    arrange_valid_state_for_kind(final_ctx, kind)
    before = final_counts_and_projection(final_ctx)
    injected = IntegrityError("injected", {}, Exception("injected"))
    def fail():
        raise injected
    kwargs = {"before_decision_insert": fail} if seam == "decision" else {
        "before_outbox_insert": fail
    }
    factory = cast(Callable[[], UnitOfWork], partial(final_ctx.store.uow_factory, **kwargs))
    service = FinanceDecisionService(factory, actors=final_ctx.actors,
        clock=lambda: FINALIZED_AT)
    reason = "reject" if kind is DecisionKind.REJECTED else None
    with pytest.raises(IntegrityError) as raised:
        service.finalize(finalize_command(final_ctx, kind, reason=reason), final_ctx.alex)
    assert raised.value is injected
    assert final_counts_and_projection(final_ctx) == before

def test_approved_decision_reopens_and_reads_after_finance_supersession(final_ctx):
    decision = finalize_approved(final_ctx)
    persist_later_analysis_and_selection(final_ctx)
    url = str(final_ctx.store.engine.url)
    final_ctx.store.engine.dispose()
    reopened = SqliteStore(build_sqlite_engine(url), runtime_mode=RuntimeMode.FALLBACK)
    try:
        with reopened.uow_factory() as uow:
            assert uow.decisions.get(decision.decision_id) == decision
    finally:
        reopened.engine.dispose()

def test_alex_and_taylor_rejection_paths_emit_zero_events(final_ctx):
    final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    final_ctx.finance.resolve(resolution(final_ctx), final_ctx.taylor)
    assert final_row_counts(final_ctx)[2] == 0
    persist_later_analysis_and_selection(final_ctx)
    reject_current_analysis(final_ctx, key="alex-reject")
    assert final_row_counts(final_ctx)[2] == 0

def test_backward_high_cost_approval_time_rolls_back(final_ctx):
    approved = submit_and_approve(final_ctx)
    before = final_counts_and_projection(final_ctx)
    high = FinanceDecisionService(final_ctx.store.uow_factory,
        actors=final_ctx.actors,
        clock=lambda: approved.resolution.review.reviewed_at - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        high.finalize(finalize_command(final_ctx, DecisionKind.APPROVED), final_ctx.alex)
    assert final_counts_and_projection(final_ctx) == before

def test_backward_low_cost_approval_time_rolls_back(final_ctx):
    selected = submit_low_cost(final_ctx, "RL-OPTION-TRANSFER")
    before = final_counts_and_projection(final_ctx)
    service = FinanceDecisionService(final_ctx.store.uow_factory,
        actors=final_ctx.actors,
        clock=lambda: selected.selection.submitted_at - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        service.finalize(
            finalize_command(final_ctx, DecisionKind.APPROVED), final_ctx.alex
        )
    assert final_counts_and_projection(final_ctx) == before

def test_backward_low_cost_withdrawal_rolls_back(final_ctx):
    selected = submit_low_cost(final_ctx, "RL-OPTION-TRANSFER")
    before = final_counts_and_projection(final_ctx)
    service = FinanceDecisionService(final_ctx.store.uow_factory,
        actors=final_ctx.actors,
        clock=lambda: selected.selection.submitted_at - timedelta(seconds=1))
    with pytest.raises(ValueError, match="precede proposal submission"):
        service.finalize(finalize_command(
            final_ctx, DecisionKind.REJECTED, reason="withdraw"
        ), final_ctx.alex)
    assert final_counts_and_projection(final_ctx) == before
```

Add the imports shown in the fixture block for `OperationalError`, `insert`, `analysis_versions`, and `case_proposal_selections`, then add these executable corruption and race tests:

```python
@pytest.mark.parametrize(
    ("mutation", "option_id", "cost"),
    (
        ("another_option", "RL-OPTION-TRANSFER", "2250.00"),
        ("wrong_cost", "RL-OPTION-COMBINED", "1.00"),
        ("baseline", "RL-OPTION-NO-MITIGATION", "0.00"),
        ("blocked", "RL-OPTION-BETA", "0.00"),
        ("infeasible", "RL-OPTION-BETA", "0.00"),
    ),
)
def test_approval_rejects_mismatched_current_material(
    final_ctx, mutation, option_id, cost
):
    submitted = final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    assert submitted.review is not None
    command = finalize_command(final_ctx, DecisionKind.APPROVED)
    before_rows = final_row_counts(final_ctx)
    before_generation = command.expected.generation
    with final_ctx.store.engine.begin() as connection:
        raw = connection.scalar(select(case_proposal_selections.c.payload_json).where(
            case_proposal_selections.c.selection_id == submitted.selection.selection_id
        ))
        payload = json.loads(raw)
        payload["selection"]["proposal"]["option_id"] = option_id
        payload["selection"]["proposal"]["response_cost"] = cost
        connection.execute(update(case_proposal_selections).where(
            case_proposal_selections.c.selection_id == submitted.selection.selection_id
        ).values(payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":"))))
    with pytest.raises(PersistenceIntegrityError, match="proposal|selection|option"):
        final_ctx.finalizer.finalize(command, final_ctx.alex)
    assert final_row_counts(final_ctx) == before_rows, mutation
    with final_ctx.store.engine.connect() as connection:
        assert connection.scalar(select(case_projection.c.proposal_generation).where(
            case_projection.c.case_id == final_ctx.case.case_id
        )) == before_generation

def test_equal_hash_different_analysis_id_cannot_finalize(final_ctx):
    submitted = final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    command = finalize_command(final_ctx, DecisionKind.APPROVED)
    other_id = "RL-ANALYSIS-EQUAL-HASH-DIFFERENT-ID"
    with final_ctx.store.engine.begin() as connection:
        analysis_row = dict(connection.execute(select(analysis_versions).where(
            analysis_versions.c.analysis_id == final_ctx.analysis.analysis_id
        )).mappings().one())
        analysis_payload = json.loads(analysis_row["payload_json"])
        analysis_payload["analysis_id"] = other_id
        analysis_row["analysis_id"] = other_id
        analysis_row["payload_json"] = json.dumps(
            analysis_payload, sort_keys=True, separators=(",", ":")
        )
        connection.execute(insert(analysis_versions).values(**analysis_row))
        raw = connection.scalar(select(case_proposal_selections.c.payload_json).where(
            case_proposal_selections.c.selection_id == submitted.selection.selection_id
        ))
        payload = json.loads(raw)
        payload["selection"]["proposal"]["analysis_id"] = other_id
        payload["expected"]["analysis_id"] = other_id
        connection.execute(update(case_proposal_selections).where(
            case_proposal_selections.c.selection_id == submitted.selection.selection_id
        ).values(analysis_id=other_id,
            payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":"))))
    before = final_row_counts(final_ctx)
    with pytest.raises(PersistenceIntegrityError):
        final_ctx.finalizer.finalize(
            command, final_ctx.alex
        )
    assert final_row_counts(final_ctx) == before

def test_standing_finance_without_real_approved_review_cannot_finalize(final_ctx):
    final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
    assert not any(item.role == "finance_approver"
        for item in final_ctx.analysis.approval_satisfactions)
    before = final_counts_and_projection(final_ctx)
    with pytest.raises(FinanceFinalizationInvalid, match="lacks Finance approval"):
        final_ctx.finalizer.finalize(
            finalize_command(final_ctx, DecisionKind.APPROVED), final_ctx.alex
        )
    assert final_counts_and_projection(final_ctx) == before

@pytest.mark.parametrize("mutation", ("selection_snapshot", "review_snapshot", "review_revision"))
def test_persisted_proposal_evidence_corruption_is_rejected(final_ctx, mutation):
    decision = finalize_approved(final_ctx)
    with final_ctx.store.engine.begin() as connection:
        raw = connection.scalar(select(decisions.c.payload_json).where(
            decisions.c.decision_id == decision.decision_id
        ))
        payload = json.loads(raw)
        evidence = payload["proposal_approval"]
        if mutation == "selection_snapshot":
            evidence["selection"]["submitted_by"]["display_name"] = "tampered"
        elif mutation == "review_snapshot":
            evidence["review"]["reason"] = "tampered"
        else:
            evidence["review_revision"] += 1
        connection.execute(update(decisions).where(
            decisions.c.decision_id == decision.decision_id
        ).values(payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":"))))
    checks = (
        lambda uow: uow.decisions.get(decision.decision_id),
        lambda uow: uow.decisions.list_for_case(decision.case_id),
        lambda uow: uow.execution.insert_outbox(
            ActionPlanningRequested.for_decision(decision)
        ),
    )
    for check in checks:
        with pytest.raises(PersistenceIntegrityError):
            with final_ctx.store.uow_factory() as uow:
                check(uow)

def _sqlite_lock_or_raise(error):
    original = error.orig
    code = getattr(original, "sqlite_errorcode", None)
    if code is None or (code & 0xFF) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        raise error
    return "lock"

@pytest.mark.parametrize(
    "operation",
    ("identical", "different_approval_key", "proposal_publish", "analysis_save", "taylor_resolve"),
)
def test_file_sqlite_finalization_races(final_ctx, monkeypatch, operation):
    if operation == "taylor_resolve":
        final_ctx.finance.submit(submission(final_ctx), final_ctx.alex)
        primary = finalize_command(
            final_ctx, DecisionKind.REJECTED, key="race-reject", reason="withdraw"
        )
        resolve_command = resolution(final_ctx, approved=True, reason=None)
        other_call = lambda: final_ctx.finance.resolve(
            resolve_command, final_ctx.taylor
        )
    else:
        submit_and_approve(final_ctx)
        primary = finalize_command(final_ctx, DecisionKind.APPROVED, key="race-final")
        if operation == "identical":
            other_call = lambda: final_ctx.finalizer.finalize(primary, final_ctx.alex)
        elif operation == "different_approval_key":
            other = primary.model_copy(update={"idempotency_key": "race-other"})
            other_call = lambda: final_ctx.finalizer.finalize(other, final_ctx.alex)
        elif operation == "proposal_publish":
            replacement = submission(final_ctx, "RL-OPTION-TRANSFER", "race-publish")
            other_call = lambda: final_ctx.finance.submit(replacement, final_ctx.alex)
        else:
            analysis_id = "RL-ANALYSIS-RACE-LATER"
            later = analyze_case(AnalyzeCaseCommand(
                analysis_id=analysis_id, case=final_ctx.case,
                corpus=CorpusScope.DEMO_CORPUS,
                operational_snapshot=final_ctx.snapshot,
                evidence_items=build_rl001_evidence(final_ctx.snapshot,
                    analysis_id=analysis_id, retrieved_at=FINALIZED_AT),
                analysis_started_at=FINALIZED_AT, created_at=FINALIZED_AT,
                calculation_version="rl001-options-v1",
            ))
            other_call = lambda: final_ctx.store.save_analysis(later)
    # Both transactions must read before either writes. A barrier at CAS is
    # too late: publication/analysis may already hold SQLite's writer lock.
    from threading import local
    synchronization = local()
    barrier = Barrier(2, timeout=5)
    original = proposals_module.SqlAlchemyProposalRepository.get_state
    def synchronized_state(repository, case_id):
        state = original(repository, case_id)
        if getattr(synchronization, "first_read", False):
            synchronization.first_read = False
            barrier.wait()
        return state
    monkeypatch.setattr(proposals_module.SqlAlchemyProposalRepository,
        "get_state", synchronized_state)
    def invoke(call):
        try:
            synchronization.first_read = True
            return call()
        except OperationalError as error:
            return _sqlite_lock_or_raise(error)
        except (FinanceCommandConflict, FinanceFinalizationConflict, StaleProposal,
                FinanceReviewRevisionConflict) as error:
            return error
        except BaseException:
            barrier.abort()
            raise
    calls = (
        lambda: final_ctx.finalizer.finalize(primary, final_ctx.alex), other_call
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(invoke, call) for call in calls]
        results = [future.result(timeout=15) for future in futures]
    decisions_won = [item for item in results if isinstance(item, Decision)]
    if operation == "identical":
        assert len(decisions_won) in (1, 2)
        if len(decisions_won) == 2:
            assert decisions_won[0] == decisions_won[1]
    else:
        assert len(decisions_won) <= 1
    with final_ctx.store.uow_factory() as uow:
        stored = uow.decisions.list_for_case(final_ctx.case.case_id)
    assert len(stored) <= 1
    approved_count = sum(item.kind is DecisionKind.APPROVED for item in stored)
    assert final_row_counts(final_ctx)[1] == approved_count
    assert final_row_counts(final_ctx)[2] == approved_count
```

Expected RED: missing command/service and evidence persistence binding.

- [ ] **Step 8: Add the strict finalization command**

In `services/finance/contracts.py`:

```python
class FinalizeProposalCommand(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: Identifier
    expected: ProposalToken
    kind: DecisionKind
    idempotency_key: CommandKey
    rejection_reason: Annotated[StrictStr, Field(max_length=4000)] | None = None

    @field_validator("case_id", "idempotency_key")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be nonblank")
        return value

    @field_validator("rejection_reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def request_shape(self) -> "FinalizeProposalCommand":
        if self.expected.analysis_id is None or self.expected.analysis_material_hash is None:
            raise ValueError("finalization requires a current analysis")
        if self.kind is DecisionKind.APPROVED:
            if self.expected.selection_id is None:
                raise ValueError("approval requires a current proposal selection")
            if self.rejection_reason is not None:
                raise ValueError("approval cannot include rejection_reason")
        elif self.rejection_reason is None:
            raise ValueError("rejection requires a nonblank rejection_reason")
        return self
```

Unknown client cost, option, actor, evidence, review, Decision ID, and timestamps are rejected by `extra="forbid"`.

- [ ] **Step 9: Implement exact-identity `FinanceDecisionService`**

Create `services/finance/decisions.py`. Define `FinanceFinalizationConflict`, `FinanceFinalizationInvalid`, and use this complete control flow (imports are the named domain/service/repository types already listed in this task):

```python
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from data.domain.cases import WorkflowVersion
from data.domain.decisions import Decision, DecisionKind, IdentitySnapshot, RecordDecisionCommand
from data.domain.execution import ActionPlanningRequested
from data.domain.finance import FinanceReviewStatus
from data.domain.finance_decisions import ProposalApprovalEvidence
from data.domain.proposals import ProposalState
from services.decisions.service import DecisionPolicy
from services.finance.contracts import FinalizeProposalCommand
from services.finance.identity import BoundFinanceActors, authority_material
from services.persistence.finance_reviews import FinanceReviewIdempotencyConflict, FinanceReviewRevisionConflict
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal
from services.policy.thresholds import requires_finance_approval


class FinanceFinalizationConflict(RuntimeError):
    pass


class FinanceFinalizationInvalid(ValueError):
    pass


def finalization_fingerprint(
    command: FinalizeProposalCommand, actor: IdentitySnapshot
) -> str:
    material = {
        "operation": "finance-finalize",
        "command": command.model_dump(mode="json"),
        "actor": authority_material(actor),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


FINALIZATION_CONTENTION = (
    IntegrityError,
    StaleProposal,
    FinanceReviewIdempotencyConflict,
    FinanceReviewRevisionConflict,
)


class FinanceDecisionService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], *,
        actors: BoundFinanceActors, policy: DecisionPolicy | None = None,
        clock: Callable[[], datetime] | None = None) -> None:
        self._uow_factory = uow_factory
        self._actors = actors
        self._policy = policy or DecisionPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise FinanceFinalizationInvalid("Server clock must be timezone-aware")
        return now

    @staticmethod
    def _already_approved(uow, case_id: str, selection_id: str) -> bool:
        return any(
            item.kind is DecisionKind.APPROVED
            and item.proposal_approval is not None
            and item.proposal_approval.selection.selection_id == selection_id
            for item in uow.decisions.list_for_case(case_id)
        )

    def _return_existing(self, decision: Decision, fingerprint: str) -> Decision:
        if decision.request_fingerprint != fingerprint:
            raise FinanceFinalizationConflict("Key was used for another finalization")
        self._actors.require_alex(decision.actor)
        if decision.proposal_approval is not None:
            self._actors.require_alex(
                decision.proposal_approval.selection.submitted_by
            )
        return decision

    def _evidence(self, state: ProposalState) -> ProposalApprovalEvidence:
        selection = state.selection
        if selection is None:
            raise FinanceFinalizationInvalid("Approval requires current selection")
        self._actors.require_alex(selection.submitted_by)
        if requires_finance_approval(selection.proposal.response_cost):
            review = state.review
            if (
                review is None or state.review_revision is None
                or review.status is not FinanceReviewStatus.APPROVED
                or review.reviewed_by is None
            ):
                raise FinanceFinalizationInvalid(
                    "Current proposal lacks Finance approval"
                )
            self._actors.require_taylor(review.reviewed_by)
            return ProposalApprovalEvidence(
                selection=selection,
                review=review,
                review_revision=state.review_revision,
            )
        return ProposalApprovalEvidence(
            selection=selection, review=None, review_revision=None
        )

    def _once(
        self, command: FinalizeProposalCommand, actor: IdentitySnapshot,
        *, key: str, fingerprint: str,
    ) -> Decision:
        with self._uow_factory() as uow:
            existing = uow.decisions.get_by_idempotency_key(key)
            if existing is not None:
                return self._return_existing(existing, fingerprint)
            state = uow.proposals.get_state(command.case_id)
            if state.token != command.expected:
                raise StaleProposal("Case analysis or proposal changed")
            if state.selection is not None:
                self._actors.require_alex(state.selection.submitted_by)
            projection = uow.cases.get_projection(command.case_id)
            case = projection.case
            if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
                raise FinanceFinalizationInvalid(
                    "Independent Finance workflow is required"
                )
            analysis_id = command.expected.analysis_id
            if analysis_id is None:
                raise FinanceFinalizationInvalid("Current analysis is required")
            analysis = uow.cases.get_analysis(analysis_id)
            if (
                analysis.case_id != command.case_id
                or analysis.material_hash != command.expected.analysis_material_hash
            ):
                raise StaleProposal("Analysis binding changed")
            evidence = None
            option_id = None
            if command.kind is DecisionKind.APPROVED:
                evidence = self._evidence(state)
                option_id = evidence.selection.proposal.option_id
                if self._already_approved(
                    uow, command.case_id, evidence.selection.selection_id
                ):
                    raise FinanceFinalizationConflict(
                        "Current proposal selection was already finalized"
                    )
            elif (
                state.selection is not None
                and self._already_approved(
                    uow, command.case_id, state.selection.selection_id
                )
            ):
                raise FinanceFinalizationConflict(
                    "Finalized selection belongs to active execution"
                )
            record = RecordDecisionCommand(
                case_id=command.case_id,
                analysis_id=analysis.analysis_id,
                selected_option_id=option_id,
                kind=command.kind,
                idempotency_key=key,
                rejection_reason=command.rejection_reason,
            )
            satisfactions = self._policy.authorize_independent_and_materialize(
                record, actor, case, projection, analysis, evidence
            )
            decided_at = self._now()
            decision = Decision.from_command(
                record, actor, analysis, satisfactions,
                request_fingerprint=fingerprint,
                decided_at=decided_at,
                proposal_approval=evidence,
            )
            if command.kind is DecisionKind.APPROVED:
                uow.proposals.guard_current(command.case_id, expected=command.expected)
            else:
                uow.proposals.withdraw_current(
                    command.case_id,
                    expected=command.expected,
                    now=decided_at,
                    operation_id=decision.decision_id,
                )
            uow.decisions.insert(decision)
            uow.decisions.insert_satisfactions(
                decision.decision_id, satisfactions
            )
            if command.kind is DecisionKind.APPROVED:
                uow.execution.insert_outbox(
                    ActionPlanningRequested.for_decision(decision)
                )
                uow.cases.set_current_decision(
                    decision.case_id, decision.decision_id
                )
            else:
                uow.cases.mark_rejected(decision.case_id, decision.decision_id)
            uow.commit()
            return decision

    def finalize(
        self, command: FinalizeProposalCommand, actor: IdentitySnapshot
    ) -> Decision:
        self._actors.require_alex(actor)
        key = f"finance-finalize:{command.idempotency_key}"
        fingerprint = finalization_fingerprint(command, actor)
        try:
            return self._once(
                command, actor, key=key, fingerprint=fingerprint
            )
        except FINALIZATION_CONTENTION as error:
            self._actors.require_alex(actor)
            with self._uow_factory() as uow:
                existing = uow.decisions.get_by_idempotency_key(key)
                if existing is not None:
                    return self._return_existing(existing, fingerprint)
                if uow.proposals.get_state(command.case_id).token != command.expected:
                    raise FinanceFinalizationConflict(
                        "Finalization lost a current-state race"
                    ) from error
            raise
```

The persistence key is `finance-finalize:{command.idempotency_key}`. Keep these exception bases and catch tuple exact; `OperationalError` is deliberately absent.

`finalize` sequence is exact:

1. Require Alex before fingerprint/UoW.
2. Open one UoW and return matching namespaced receipt before clock access.
3. Require `get_state(case_id).token == command.expected`.
4. Require independent workflow; load expected analysis and verify case ID/material hash.
5. For both kinds, if a current selection exists, require its submitter to be the exact configured Alex before any duplicate check or mutation. Approval then requires an executable selection. Above 20000 require latest state review approved by configured Taylor and build evidence with its exact revision; at/below 20000 build evidence without review. Scan all case Decisions for duplicate selection.
6. Rejection: after the same owner check, scan the current selection ID when present and reject withdrawal if an approved Decision already embeds it.
7. Build internal server-owned `RecordDecisionCommand`: current analysis ID; current option only for approval; rejection reason only for rejection; namespaced key.
8. Call `authorize_independent_and_materialize`; read one aware clock value; build `Decision.from_command` with `proposal_approval=evidence`.
9. Approval calls `guard_current`; rejection calls `withdraw_current(operation_id=decision.decision_id)`. Never both.
10. Insert Decision and satisfactions. Approval inserts one outbox and sets current Decision. Rejection inserts no event and calls `mark_rejected`. Commit once.

Catch only `IntegrityError`, `StaleProposal`, `FinanceReviewIdempotencyConflict`, and `FinanceReviewRevisionConflict`. After losing UoW exit, reauthorize Alex, open a fresh UoW, return matching receipt, or raise `FinanceFinalizationConflict` if state changed; otherwise re-raise the original error. Never catch `OperationalError`.

- [ ] **Step 10: Validate exact historical evidence in persistence**

Add and call from `_require_analysis_lineage`:

```python
    def _require_proposal_lineage(self, decision: Decision) -> None:
        evidence = decision.proposal_approval
        independent = decision.approval_policy_version == WorkflowVersion.INDEPENDENT_FINANCE.value
        if decision.kind is DecisionKind.REJECTED:
            if evidence is not None:
                raise PersistenceIntegrityError("Rejected Decision has proposal evidence")
            return
        if independent != (evidence is not None):
            raise PersistenceIntegrityError("Decision proposal evidence conflicts with policy")
        if evidence is None:
            return
        from services.persistence.finance_reviews import SqlAlchemyFinanceReviewRepository
        from services.persistence.proposals import SqlAlchemyProposalRepository
        selection = SqlAlchemyProposalRepository(self._store, self._connection).get_selection(
            evidence.selection.selection_id
        )
        if selection != evidence.selection:
            raise PersistenceIntegrityError("Decision selection snapshot differs from journal")
        if evidence.review is None:
            if evidence.review_revision is not None:
                raise PersistenceIntegrityError("Low-cost evidence has review revision")
            return
        if evidence.review_revision is None:
            raise PersistenceIntegrityError("Finance evidence lacks revision")
        review = SqlAlchemyFinanceReviewRepository(self._store, self._connection).get_revision(
            evidence.review.review_id, evidence.review_revision
        )
        if review != evidence.review:
            raise PersistenceIntegrityError("Decision Finance snapshot differs from revision")
```

In `insert`, call complete `_require_analysis_lineage(decision)` before inserting the Decision, replacing the partial provenance condition. It does not call bound-row or outbox-cardinality checks, so same-transaction ordering remains valid. In `_require_derived_satisfactions`, calculate current roles then `discard("finance_approver")` only when policy is independent. Preserve every other exact role check.

- [ ] **Step 11: Run complete verification**

```bash
.venv/bin/python -m pytest tests/finance/test_finance_final_decision.py -q -m 'not fabric_live' -o addopts=''
.venv/bin/python -m pytest tests/finance/test_workflow_policy.py tests/persistence/test_decision_outbox.py tests/persistence/test_sqlite_store.py tests/persistence/test_finance_reviews.py -q -m 'not fabric_live' -o addopts=''
.venv/bin/python -m pytest tests/domain tests/finance tests/auth tests/persistence tests/integration/test_store_contract.py tests/api/test_case_lifecycle.py -q -m 'not fabric_live' -o addopts=''
.venv/bin/pyright --pythonpath .venv/bin/python data/domain/decisions.py data/domain/finance_decisions.py services/decisions/service.py services/finance services/persistence/store.py services/persistence/proposals.py services/persistence/ports.py tests/finance/test_finance_final_decision.py
.venv/bin/ruff check data/domain/decisions.py data/domain/finance_decisions.py services/decisions/service.py services/finance services/persistence/store.py services/persistence/proposals.py services/persistence/ports.py tests/finance/test_finance_final_decision.py tests/finance/test_workflow_policy.py tests/persistence/test_decision_outbox.py
.venv/bin/ruff format --check data/domain/decisions.py data/domain/finance_decisions.py services/decisions/service.py services/finance services/persistence/store.py services/persistence/proposals.py services/persistence/ports.py tests/finance/test_finance_final_decision.py tests/finance/test_workflow_policy.py tests/persistence/test_decision_outbox.py
git diff --check
git diff --exit-code -- tests/finance/fixtures/legacy-policy.json
```

Expected: all selected non-live tests pass; Pyright has 0 errors; Ruff and whitespace pass; frozen fixture has no diff. Record exact counts and warnings.

- [ ] **Step 12: Report, scoped commit, independent review**

Write `.superpowers/sdd/finance-final-decision-task-report.md` with RED/GREEN evidence, every acceptance group mapped to actual test names, rollback/race results, warnings, scope/deviations, frozen-fixture result, self-review, and SHA.

```bash
git add data/domain/decisions.py data/domain/finance_decisions.py services/decisions/service.py services/finance/contracts.py services/finance/decisions.py services/persistence/ports.py services/persistence/proposals.py services/persistence/store.py tests/finance/test_finance_final_decision.py tests/finance/test_workflow_policy.py tests/persistence/test_decision_outbox.py
git commit -m "feat: bind final Decisions to Finance proposals"
```

Expected: one coherent commit without README/roadmap, API/UI, schema/migration, fixture, execution activation, or live changes. Request independent Spec and Quality review over the immutable base-to-SHA range; fix and re-review before adoption.

## Self-Review Checklist

- [ ] Exact current selection and exact approved Finance revision are embedded for high-cost approval; low-cost embeds no review.
- [ ] Rejection with no selection or pending/approved selection is atomic withdrawal, never fabricated Taylor rejection.
- [ ] Low-cost withdrawal enforces aware/non-backward chronology.
- [ ] Exact Alex authorization precedes initial/replay/recovery UoWs.
- [ ] Duplicate approval scans validated history even when the current Decision pointer changes.
- [ ] Independent policy excludes Finance from unsatisfied scanning and candidate selection, preserving all non-Finance prerequisites.
- [ ] Insert/read compare complete historical snapshots at exact revision without latest/current comparison.
- [ ] Guard/withdrawal, Decision, satisfactions, event, and projection commit once and roll back together.
- [ ] Legacy fingerprints, service behavior, serialization, satisfactions, and frozen bytes remain unchanged except deliberate rejection of independent cases/receipts.
- [ ] No API/UI/schema/live/execution activation exists; later execution-currentness guard remains mandatory.

## Parent adoption clarifications

- Code examples must be reconciled to actual typed repository interfaces during
  RED/GREEN; do not preserve a faulty test fixture merely to transcribe a plan.
  Binding invariants and all acceptance groups remain mandatory.
- For concurrency tests, synchronize the first transaction state read, before
  either writer has written. Prebuild commands outside the barrier. Do not wait
  at a CAS after another insert holds SQLite's writer lock. Confirm both distinct
  connections crossed the barrier and assert the operation-specific durable
  winner; accepting two failures or only asserting row counts <= 1 is insufficient.
  Remove the patch before eventual identical-key replay; require the exact
  original Decision and one event. Include selection/review/projection rows in
  loser-rollback assertions, not just Decision and event counts.
- The pending-only test is not proof that injected standing Finance authorization
  is rejected. Exercise the actual forged/injected standing material boundary,
  or name an existing concrete golden/negative test establishing that requirement.
  Similarly, blocked and infeasible test cases must test distinct causes or be
  combined honestly; duplicate tampering labelled as two different proofs is not
  sufficient. Corruption setup must assert its intended mismatched field first.
- Preserve rejected Decision shape validation and exact configured ownership on
  both approval and withdrawal. Preserve all feasible option finalization; do not
  introduce a combined-only restriction here. Option-specific execution and fresh
  execution guards remain required subsequent tasks before new-policy activation.
- No live deployment, tenant change, schema application, actual approval, Graph
  call or real email send is authorized by this local implementation task.

