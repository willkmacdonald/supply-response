# Exact-Identity Finance Application Services Implementation Plan

Parent-reviewed plan, September 13, 2026. Finance proposal selection is accepted
at `42ee347` after independent review and a fresh 312-pass non-live regression.
Consumed interfaces below match that accepted implementation. Task A must pass
its own review before Task B; neither task activates routes or changes live data.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the exact configured Alex submit durable response selections and the exact configured Taylor resolve Finance requests, with stable command replay and authenticated current/historical read models.

**Architecture:** Consume the adopted selection repository's `publish(SelectionReceipt)` and `guard_current()` inside application-owned UoWs. Submission returns its original selection and pending review revision; resolution returns its original terminal revision; current status remains a separate query. Read-only repository queries identify exact historical selections and current pending candidates without changing schema.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy Core, existing SQLite/Fabric adapters, pytest.

## Preconditions and constraints

- Based on adopted `docs/superpowers/plans/2026-09-13-finance-proposal-selection.md`, implemented and accepted through `42ee347`.
- Use the writing-plans review/test discipline. Two reviewable tasks: complete command service, then authenticated read models. Neither activates routes. All command transaction wiring lands together in Task A.
- No HTTP, UI, final Decision, deployment, auth token verification/composition, tenant provisioning, mail, outbox creation or live calls. This layer consumes server-authenticated `IdentitySnapshot`; the next API plan must prove bearer-token binding.
- Exact configured tenant/object, ENTRA source, persona/source IDs and exact effective roles are checked **before all reads/replay**, including contention recovery. Alex and Taylor object IDs must differ.
- Cost comes from the actual immutable evaluated option. `> 20000` creates a pending review; `<= 20000` publishes selection with no FinanceReview. Baseline/infeasible options fail.
- Same command key/content returns original server IDs/times even after later resolution/supersession. Different expected token/revision with the same key conflicts. Auth runs before returning those records.
- Display name/principal-name changes do not change authority. Fingerprint stable authority facts and normalized command fields; persist full authenticated identity snapshots in review/selection audit. This explicit choice allows a repeated command after display-name refresh to replay its original audit snapshot.
- Rejected unchanged resubmission with a new key creates new selection/review IDs. A repeated old key returns its old result. A low-cost selection after rejection creates no review.
- No `append_finance_review` transaction-owning facade inside service UoWs; no savepoints, production test hooks or automatic retry that overwrites a competing winner.
- No metadata changes are needed; query additions use accepted 0008 columns/indexes. Historical canonical payloads remain unchanged.
- Every test command includes `-m 'not fabric_live'`; actual Fabric concurrency remains a separate release gate.

## Consumed repository contracts

`uow.proposals`: `get_state(case_id) -> ProposalState`, `get_selection(selection_id) -> ProposalSelection`, `get_by_idempotency_key(key) -> SelectionReceipt | None`, `publish(receipt) -> ProposalSelection`, `guard_current(case_id, expected=token) -> ProposalToken`.

`uow.finance_reviews`: `get_latest(review_id) -> (review, revision)`, `get_revision(review_id, revision) -> review`, `get_by_idempotency_key(key) -> (review, revision, fingerprint) | None`, and `append(review, expected_revision=..., idempotency_key=..., request_fingerprint=...) -> (review, revision)`.

`uow.cases.get_projection` and `get_analysis` use the UoW connection. Do not use `get_case` delegation, which opens a separate store connection.

## Task 1: Complete submission/resolution and command replay (Task A)

**Files:** create `services/finance/identity.py`, `services/finance/contracts.py`, `services/finance/service.py`, `tests/finance/test_finance_service.py`. No new package index is necessary: existing services use namespace-package directories.

### A1: Exact identities and command/result value types

- [ ] Add tests first for wrong tenant/object/source/persona, extra/missing roles, same Alex/Taylor object, malformed UUID, caller-supplied cost/time/actor/unknown field, blank keys and rejection reason, nonboolean approval and bool revision. Every rejected command must leave persistence counts unchanged.
- [ ] Create `services/finance/identity.py` with:

```python
from uuid import UUID
from pydantic import model_validator
from data.domain.common import FrozenModel
from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource

class FinancePermissionDenied(PermissionError):
    pass

class BoundFinanceActors(FrozenModel):
    tenant_id: UUID
    alex_object_id: UUID
    taylor_object_id: UUID

    @model_validator(mode='after')
    def different_people(self):
        if self.alex_object_id == self.taylor_object_id:
            raise ValueError('Alex and Taylor must be different people')
        return self

    def _require(self, actor: IdentitySnapshot, *, taylor: bool) -> None:
        name = 'TAYLOR' if taylor else 'ALEX'
        roles = ('finance_approver',) if taylor else ('material_planner', 'response_approver')
        try:
            tenant, object_id = UUID(actor.tenant_id or ''), UUID(actor.object_id or '')
        except (ValueError, TypeError, AttributeError) as error:
            raise FinancePermissionDenied('Exact configured Finance workflow identity required') from error
        if (tenant != self.tenant_id
            or object_id != (self.taylor_object_id if taylor else self.alex_object_id)
            or actor.identity_source is not IdentitySource.ENTRA
            or actor.persona_id != f'RL-PERSONA-{name}'
            or actor.source_id != f'RL-ENTRA-{name}'
            or actor.effective_roles != roles):
            raise FinancePermissionDenied('Exact configured Finance workflow identity required')

    def require_alex(self, actor: IdentitySnapshot) -> None:
        self._require(actor, taylor=False)

    def require_taylor(self, actor: IdentitySnapshot) -> None:
        self._require(actor, taylor=True)

def authority_material(actor: IdentitySnapshot) -> dict:
    return dict(tenant_id=str(UUID(actor.tenant_id or '')),
        object_id=str(UUID(actor.object_id or '')), identity_source=actor.identity_source.value,
        persona_id=actor.persona_id, source_id=actor.source_id,
        effective_roles=actor.effective_roles)
```

- [ ] Create `services/finance/contracts.py` with:

```python
from typing import Annotated
from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator
from data.domain.common import FrozenModel
from data.domain.finance import FinanceReview
from data.domain.proposals import ProposalSelection, ProposalToken

Identifier = Annotated[StrictStr, Field(min_length=1, max_length=128)]
CommandKey = Annotated[StrictStr, Field(min_length=1, max_length=200)]

class SubmitProposalCommand(FrozenModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    case_id: Identifier
    option_id: Identifier
    expected: ProposalToken
    idempotency_key: CommandKey

    @field_validator('case_id', 'option_id', 'idempotency_key')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('value must be nonblank')
        return value

    @model_validator(mode='after')
    def analyzed(self):
        if self.expected.analysis_id is None or self.expected.analysis_material_hash is None:
            raise ValueError('submission requires an analyzed case')
        return self

class ResolveFinanceCommand(FrozenModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    review_id: Identifier
    expected: ProposalToken
    expected_review_revision: StrictInt = Field(gt=0)
    approved: StrictBool
    reason: Annotated[StrictStr, Field(max_length=4000)] | None = None
    idempotency_key: CommandKey

    @field_validator('review_id', 'idempotency_key')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('value must be nonblank')
        return value

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        return (value.strip() or None) if value is not None else None

    @model_validator(mode='after')
    def request_shape(self):
        if not self.approved and self.reason is None:
            raise ValueError('rejection requires a nonblank reason')
        if self.expected.selection_id is None or self.expected.analysis_id is None:
            raise ValueError('resolution requires a current proposal selection')
        return self

class SubmissionResult(FrozenModel):
    selection: ProposalSelection
    review: FinanceReview | None
    review_revision: int | None

class ResolutionResult(FrozenModel):
    review: FinanceReview
    review_revision: int
```

The submitted analysis ID/hash come from `expected`; do not add redundant independent analysis fields. Server ignores no unknown material: command parsing rejects extra fields.

### A2: Service code and transaction ownership

- [ ] Create `services/finance/service.py` with the complete command implementation below. The only later addition to this class is Task B's read methods.

```python
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from data.domain.analysis import AnalysisResponseOptionMaterial
from data.domain.cases import WorkflowVersion
from data.domain.decisions import IdentitySnapshot
from data.domain.finance import FinanceProposal
from data.domain.proposals import ProposalSelection, SelectionReceipt
from services.finance.contracts import SubmitProposalCommand, ResolveFinanceCommand, SubmissionResult, ResolutionResult
from services.finance.identity import BoundFinanceActors, authority_material
from services.persistence.ports import UnitOfWork
from services.persistence.proposals import StaleProposal, SelectionIdempotencyConflict
from services.persistence.finance_reviews import FinanceReviewIdempotencyConflict, FinanceReviewRevisionConflict
from services.persistence.store import PersistenceIntegrityError
from services.policy.finance_review import submit_finance_review, resolve_finance_review
from services.policy.thresholds import requires_finance_approval

class FinanceCommandConflict(RuntimeError):
    pass

class FinanceRequestInvalid(ValueError):
    pass

def _fingerprint(operation, command, actor):
    material = {'operation': operation, 'command': command.model_dump(mode='json'),
        'actor': authority_material(actor)}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

_CONTENTION = (IntegrityError, StaleProposal, SelectionIdempotencyConflict,
    FinanceReviewIdempotencyConflict, FinanceReviewRevisionConflict)

class FinanceService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], *, actors: BoundFinanceActors,
                 clock: Callable[[], datetime] | None = None):
        self._uow_factory = uow_factory
        self._actors = actors
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self):
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise FinanceRequestInvalid('Server clock must be timezone-aware')
        return now

    def _submission_replay(self, uow, key, fingerprint):
        stored = uow.proposals.get_by_idempotency_key(key)
        if stored is None:
            return None
        if stored.request_fingerprint != fingerprint:
            raise FinanceCommandConflict('Key was already used for another submission')
        self._actors.require_alex(stored.selection.submitted_by)
        return self._submission_result(uow, stored.selection)

    @staticmethod
    def _submission_result(uow, selection):
        pending = (uow.finance_reviews.get_revision(selection.finance_review_id, 1)
            if selection.finance_review_id is not None else None)
        return SubmissionResult(selection=selection, review=pending,
            review_revision=1 if pending is not None else None)

    def _resolution_replay(self, uow, key, fingerprint):
        stored = uow.finance_reviews.get_by_idempotency_key(key)
        if stored is None:
            return None
        review, revision, original_fingerprint = stored
        if original_fingerprint != fingerprint:
            raise FinanceCommandConflict('Key was already used for another review command')
        self._actors.require_alex(review.submitted_by)
        if review.reviewed_by is None:
            raise PersistenceIntegrityError('Resolution receipt lacks reviewer')
        self._actors.require_taylor(review.reviewed_by)
        return ResolutionResult(review=review, review_revision=revision)

    def submit(self, command: SubmitProposalCommand, actor: IdentitySnapshot) -> SubmissionResult:
        self._actors.require_alex(actor)
        key = f'finance-submit:{command.idempotency_key}'
        fingerprint = _fingerprint('submit', command, actor)
        try:
            with self._uow_factory() as uow:
                replay = self._submission_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                state = uow.proposals.get_state(command.case_id)
                if state.token != command.expected:
                    raise StaleProposal('Case analysis or proposal changed')
                case = uow.cases.get_projection(command.case_id).case
                if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
                    raise FinanceRequestInvalid('Independent Finance workflow is required')
                analysis_id = command.expected.analysis_id
                if analysis_id is None:
                    raise FinanceRequestInvalid('Submission requires an analyzed case')
                analysis = uow.cases.get_analysis(analysis_id)
                if analysis.case_id != case.case_id or analysis.material_hash != command.expected.analysis_material_hash:
                    raise StaleProposal('Analysis binding changed')
                option = next((o for o in analysis.response_options if o.option_id == command.option_id), None)
                material_option = next((o for o in analysis.material.response_options if o.option_id == command.option_id), None)
                if (option is None or material_option is None
                    or AnalysisResponseOptionMaterial.from_option(option) != material_option
                    or not option.executable or not option.active_mitigation
                    or option.predicted is None or option.blocking_codes):
                    raise FinanceRequestInvalid('Selected response is not executable mitigation')
                if state.selection is not None:
                    self._actors.require_alex(state.selection.submitted_by)
                now = self._now()
                proposal = FinanceProposal(case_id=case.case_id, analysis_id=analysis.analysis_id,
                    analysis_material_hash=analysis.material_hash, option_id=option.option_id,
                    response_cost=option.predicted.response_cost)
                selection_id = f'RL-SELECTION-{uuid4()}'
                review_id = f'RL-FINANCE-{uuid4()}' if requires_finance_approval(proposal.response_cost) else None
                selection = ProposalSelection(selection_id=selection_id, proposal=proposal,
                    workflow_version=case.effective_workflow_version,
                    submitted_by=actor, submitted_at=now, finance_review_id=review_id)
                if review_id is not None:
                    pending = submit_finance_review(review_id=review_id, proposal=proposal, actor=actor, now=now)
                    uow.finance_reviews.append(pending, expected_revision=None,
                        idempotency_key=f'finance-pending:{selection_id}', request_fingerprint=fingerprint)
                selection = uow.proposals.publish(SelectionReceipt(selection=selection,
                    expected=command.expected, idempotency_key=key, request_fingerprint=fingerprint))
                result = self._submission_result(uow, selection)
                uow.commit()
                return result
        except _CONTENTION as error:
            # The failed UoW has exited before this fresh replay lookup.
            self._actors.require_alex(actor)
            with self._uow_factory() as uow:
                replay = self._submission_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                state = uow.proposals.get_state(command.case_id)
                if state.token != command.expected:
                    raise FinanceCommandConflict('Submission lost a current-proposal race') from error
            raise

    def resolve(self, command: ResolveFinanceCommand, actor: IdentitySnapshot) -> ResolutionResult:
        self._actors.require_taylor(actor)
        key = f'finance-resolve:{command.idempotency_key}'
        fingerprint = _fingerprint('resolve', command, actor)
        try:
            with self._uow_factory() as uow:
                replay = self._resolution_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                review, revision = uow.finance_reviews.get_latest(command.review_id)
                self._actors.require_alex(review.submitted_by)
                state = uow.proposals.get_state(review.proposal.case_id)
                if (state.token != command.expected or state.review is None
                    or state.selection is None or state.review.review_id != command.review_id
                    or state.review != review or state.review_revision != revision
                    or revision != command.expected_review_revision):
                    raise StaleProposal('Review is no longer the expected current request')
                resolved = resolve_finance_review(review=review,
                    current_proposal=state.selection.proposal, actor=actor,
                    approved=command.approved, reason=command.reason, now=self._now())
                # Guard first, while the current read model still matches its old review.
                uow.proposals.guard_current(review.proposal.case_id, expected=command.expected)
                resolved, revision = uow.finance_reviews.append(resolved,
                    expected_revision=command.expected_review_revision,
                    idempotency_key=key, request_fingerprint=fingerprint)
                result = ResolutionResult(review=resolved, review_revision=revision)
                uow.commit()
                return result
        except _CONTENTION as error:
            self._actors.require_taylor(actor)
            with self._uow_factory() as uow:
                replay = self._resolution_replay(uow, key, fingerprint)
                if replay is not None:
                    return replay
                review, revision = uow.finance_reviews.get_latest(command.review_id)
                state = uow.proposals.get_state(review.proposal.case_id)
                if state.token != command.expected or revision != command.expected_review_revision:
                    raise FinanceCommandConflict('Review lost a current-proposal race') from error
            raise
```

Important recovery case: concurrent identical commands may generate different IDs/times before one wins. A low-level full-snapshot idempotency mismatch is therefore included in `_CONTENTION`; fresh command-fingerprint lookup returns the original winner. A different normalized command fingerprint raises `FinanceCommandConflict`. Unclassified IntegrityError with no replay and unchanged token/revision is re-raised unchanged. Operational/connection errors are not disguised as success or automatically retried.

### A3: Concrete fixtures and acceptance tests

- [ ] Put this setup in `tests/finance/test_finance_service.py`. It reuses real persisted analysis and never synthesizes Finance satisfaction evidence.

```python
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import select, func
from data.domain import CasePurpose, RuntimeMode
from data.domain.cases import WorkflowVersion
from data.domain.decisions import IdentitySnapshot, CorpusScope
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import instantiate_rl001, build_rl001_evidence
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.persistence.sqlite import sqlite_store
from services.persistence.tables import case_proposal_selections, finance_review_revisions, decisions, outbox_events
from services.finance.identity import BoundFinanceActors, FinancePermissionDenied
from services.finance.contracts import SubmitProposalCommand, ResolveFinanceCommand
from services.finance.service import FinanceService, FinanceCommandConflict

@pytest.fixture
def ctx(tmp_path):
    tenant = '11111111-1111-4111-8111-111111111111'
    alex_id, taylor_id = '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333'
    actors = BoundFinanceActors(tenant_id=tenant, alex_object_id=alex_id, taylor_object_id=taylor_id)
    alex = IdentitySnapshot(persona_id='RL-PERSONA-ALEX', source_id='RL-ENTRA-ALEX',
        identity_source=IdentitySource.ENTRA, tenant_id=tenant, object_id=alex_id,
        effective_roles=('material_planner', 'response_approver'))
    taylor = IdentitySnapshot(persona_id='RL-PERSONA-TAYLOR', source_id='RL-ENTRA-TAYLOR',
        identity_source=IdentitySource.ENTRA, tenant_id=tenant, object_id=taylor_id,
        effective_roles=('finance_approver',))
    store = sqlite_store(f'sqlite:///{tmp_path / "finance-service.db"}')
    case, snapshot = instantiate_rl001(case_id='RL-CASE-FINANCE-SERVICE',
        purpose=CasePurpose.AUTOMATED_TEST, runtime_mode=RuntimeMode.FALLBACK,
        workflow_version=WorkflowVersion.INDEPENDENT_FINANCE)
    started = datetime.fromisoformat('2026-09-01T09:01:00-05:00')
    analysis = analyze_case(AnalyzeCaseCommand(analysis_id='RL-ANALYSIS-FINANCE-SERVICE',
        case=case, corpus=CorpusScope.DEMO_CORPUS, operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(snapshot, analysis_id='RL-ANALYSIS-FINANCE-SERVICE', retrieved_at=started),
        analysis_started_at=started, created_at=started, calculation_version='rl001-options-v1'))
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    times = iter(datetime.fromisoformat('2026-09-01T14:02:00+00:00') + timedelta(minutes=i) for i in range(20))
    service = FinanceService(store.uow_factory, actors=actors, clock=lambda: next(times))
    yield SimpleNamespace(store=store, service=service, actors=actors, alex=alex,
        taylor=taylor, case=case, snapshot=snapshot, analysis=analysis)
    store.engine.dispose()

def current(ctx):
    with ctx.store.uow_factory() as uow:
        return uow.proposals.get_state(ctx.case.case_id)

def submission(ctx, option='RL-OPTION-COMBINED', key='submit-1'):
    return SubmitProposalCommand(case_id=ctx.case.case_id, option_id=option,
        expected=current(ctx).token, idempotency_key=key)

def resolution(ctx, *, approved=False, reason='Budget 10000', key='resolve-1'):
    state = current(ctx)
    return ResolveFinanceCommand(review_id=state.review.review_id, expected=state.token,
        expected_review_revision=state.review_revision, approved=approved,
        reason=reason, idempotency_key=key)

def rows(ctx):
    with ctx.store.engine.connect() as connection:
        return tuple(connection.scalar(select(func.count()).select_from(table))
            for table in (case_proposal_selections, finance_review_revisions, decisions, outbox_events))

def no_clock():
    raise AssertionError('replay must not read clock')

def test_original_submit_and_resolution_replay_after_supersession(ctx):
    submit = submission(ctx)
    first = ctx.service.submit(submit, ctx.alex)
    resolve = resolution(ctx)
    rejected = ctx.service.resolve(resolve, ctx.taylor)
    transfer = ctx.service.submit(submission(ctx, 'RL-OPTION-TRANSFER', 'submit-2'), ctx.alex)
    assert transfer.review is None and transfer.review_revision is None
    replay_service = FinanceService(ctx.store.uow_factory, actors=ctx.actors, clock=no_clock)
    assert replay_service.submit(submit, ctx.alex) == first
    assert replay_service.resolve(resolve, ctx.taylor) == rejected
    assert current(ctx).selection == transfer.selection
    assert first.review.status.value == 'pending'
    assert rejected.review.status.value == 'rejected'
    assert rows(ctx) == (2, 3, 0, 0)

def test_rejected_same_option_new_key_is_new_request(ctx):
    first = ctx.service.submit(submission(ctx), ctx.alex)
    ctx.service.resolve(resolution(ctx), ctx.taylor)
    second = ctx.service.submit(submission(ctx, key='submit-2'), ctx.alex)
    assert second.selection.selection_id != first.selection.selection_id
    assert second.review.review_id != first.review.review_id
    assert second.review.status.value == 'pending'

def test_changed_expected_same_key_conflicts(ctx):
    original = submission(ctx)
    ctx.service.submit(original, ctx.alex)
    changed = original.model_copy(update={'expected': current(ctx).token})
    with pytest.raises(FinanceCommandConflict):
        ctx.service.submit(changed, ctx.alex)

def test_authorization_precedes_replay_and_database_access(ctx, monkeypatch):
    original = submission(ctx)
    ctx.service.submit(original, ctx.alex)
    def no_database():
        raise AssertionError('unauthorized command must not open UoW')
    denied = FinanceService(no_database, actors=ctx.actors, clock=no_clock)
    with pytest.raises(FinancePermissionDenied):
        denied.submit(original, ctx.taylor)

def test_display_name_change_replays_original_identity_snapshot(ctx):
    command = submission(ctx)
    result = ctx.service.submit(command, ctx.alex)
    renamed = ctx.alex.model_copy(update={'display_name': 'Updated directory display'})
    assert ctx.service.submit(command, renamed) == result
```

- [ ] Run RED before creating service modules: `uv run pytest tests/finance/test_finance_service.py -q -m 'not fabric_live'`; expected missing imports. Then implement A1/A2 and run GREEN with the same command.
- [ ] Add parameterized permission variants to both submit and resolve (wrong tenant/object, ENTRA/source/persona, extra/missing roles, swapped actor). Use a failing UoW factory for denied calls to prove auth-before-read, not just unchanged counts. Resolve replay under Alex must fail before database access.
- [ ] Add same-key changed resolve outcome/reason/expected revision/token conflicts; approved blank reason normalizes to None; rejection blank fails model validation. Commands with client `response_cost`, `submitted_at`, `actor`, `analysis_material_hash` extras fail parsing. Exactly 20000/20000.01 use source quantity=1 and incremental unit cost target before persisting/rebuilding analysis as in selection tests.
- [ ] Inject a late `publish` CAS error after pending/receipt insertion; assert counts and pointer unchanged. Inject Finance append failure after `guard_current` in resolution; assert generation and review revision unchanged. Inject unrelated IntegrityError with unchanged state/no replay; assert the exact original exception object returns to caller.
- [ ] Add deterministic fresh-UoW recovery tests: during first attempted write, another service commits the identical command; force the first repository operation to raise its normal low-level idempotency conflict. Assert returned complete result equals winner with no losing pending row. Use a test-only monkeypatch around existing repository methods, never a production hook or savepoint.
- [ ] Add real file-SQLite concurrent same-command/different-command submit and approve/reject tests. Barriers before writes use `timeout=5`; futures use `timeout=15`; abort barrier on unexpected exception. Same command yields one durable selection/review and eventual original replay; different commands at one expected state yield one current winner and a conflict. Exclude native Fabric execution while keeping adapter contract tests parameterizable.
- [ ] Run `uv run pytest tests/finance tests/persistence/test_decision_outbox.py tests/integration/test_store_contract.py -q -m 'not fabric_live'`. Scoped commit `feat: add exact-identity Finance command services`, then independent review and any fix/re-review before acceptance.

## Task 2: Current status, exact historical detail and Taylor pending list (Task B)

**Files:** extend `services/finance/contracts.py`, `services/finance/service.py`, `services/persistence/proposals.py`, `services/persistence/ports.py` and `tests/finance/test_finance_service.py`. Reuse the same real persisted fixture; no fixture relocation or metadata/migration changes.

### B1: Narrow repository queries

- [ ] Add `get_selection_for_review(review_id: str) -> ProposalSelection` to `ProposalStore`. SQL filters existing journal `finance_review_id` (already uniquely indexed), raises `RecordNotFound` if missing, and returns `get_selection(row.selection_id)` through the same repository/connection so all immutable receipt validation stays active. Do not infer historical selection from current case pointer.
- [ ] Add `list_pending_case_ids() -> tuple[str, ...]` to `ProposalStore`. Use the existing current pointer and latest-review revision query below, returning only candidate IDs (not caller-visible records). No JSON tenant query or new tenant column is needed; service checks exact configured submitted identity after canonical decoding.

```python
latest = select(
    finance_review_revisions.c.review_id.label('review_id'),
    func.max(finance_review_revisions.c.revision).label('revision'),
).group_by(finance_review_revisions.c.review_id).subquery()
query = select(case_projection.c.case_id).select_from(
    case_projection.join(case_proposal_selections,
        case_projection.c.current_selection_id == case_proposal_selections.c.selection_id)
    .join(latest, latest.c.review_id == case_proposal_selections.c.finance_review_id)
    .join(finance_review_revisions, and_(
        finance_review_revisions.c.review_id == latest.c.review_id,
        finance_review_revisions.c.revision == latest.c.revision))
).where(finance_review_revisions.c.status == 'pending').order_by(
    case_proposal_selections.c.submitted_at, case_projection.c.case_id)
return tuple(self._connection.scalars(query))
```

Import `func`, `and_`, and the three existing tables. A historical pending revision with approved/rejected/superseded latest revision is never a candidate. A historical review with no current pointer is never a candidate. Tenant isolation remains service-enforced with exact UUID comparison, not display text.

### B2: Result model and read methods

- [ ] Add to contracts (imports `AnalysisVersion`, `ResponseOption`, `ProposalToken`):

```python
class FinanceReviewDetail(FrozenModel):
    selection: ProposalSelection
    review: FinanceReview
    review_revision: int
    analysis: AnalysisVersion
    option: ResponseOption
    is_current: bool
    current_token: ProposalToken
```

- [ ] Add imports `FinanceReviewStatus`, `ProposalState`, `FinanceReviewDetail`, and `FinancePermissionDenied` to service. Add these methods to `FinanceService`:

```python
def status(self, case_id: str, actor: IdentitySnapshot) -> ProposalState:
    self._actors.require_alex(actor)
    with self._uow_factory() as uow:
        state = uow.proposals.get_state(case_id)
        case = uow.cases.get_projection(case_id).case
        if case.effective_workflow_version is not WorkflowVersion.INDEPENDENT_FINANCE:
            raise FinanceRequestInvalid('Independent Finance workflow is required')
        if state.selection is not None:
            self._actors.require_alex(state.selection.submitted_by)
        return state

def _detail(self, uow, review_id: str) -> FinanceReviewDetail:
    selection = uow.proposals.get_selection_for_review(review_id)
    self._actors.require_alex(selection.submitted_by)
    state = uow.proposals.get_state(selection.proposal.case_id)
    review, revision = uow.finance_reviews.get_latest(review_id)
    self._actors.require_alex(review.submitted_by)
    if review.reviewed_by is not None:
        self._actors.require_taylor(review.reviewed_by)
    if review.proposal != selection.proposal or selection.finance_review_id != review_id:
        raise PersistenceIntegrityError('Historical review and selection binding differ')
    analysis = uow.cases.get_analysis(selection.proposal.analysis_id)
    option = next((o for o in analysis.response_options if o.option_id == selection.proposal.option_id), None)
    if (option is None or analysis.material_hash != selection.proposal.analysis_material_hash
        or option.predicted is None or option.predicted.response_cost != selection.proposal.response_cost):
        raise PersistenceIntegrityError('Historical review material differs from analysis')
    if uow.proposals.get_state(selection.proposal.case_id).token != state.token:
        raise StaleProposal('Review state changed while reading')
    return FinanceReviewDetail(selection=selection, review=review, review_revision=revision,
        analysis=analysis, option=option,
        is_current=state.token.selection_id == selection.selection_id,
        current_token=state.token)

def detail(self, review_id: str, actor: IdentitySnapshot) -> FinanceReviewDetail:
    self._actors.require_taylor(actor)
    with self._uow_factory() as uow:
        return self._detail(uow, review_id)

def list_pending(self, actor: IdentitySnapshot) -> tuple[FinanceReviewDetail, ...]:
    self._actors.require_taylor(actor)
    with self._uow_factory() as uow:
        results = []
        for case_id in uow.proposals.list_pending_case_ids():
            state = uow.proposals.get_state(case_id)
            if state.selection is None or state.review is None or state.review.status is not FinanceReviewStatus.PENDING:
                continue
            try:
                self._actors.require_alex(state.selection.submitted_by)
            except FinancePermissionDenied:
                continue  # Another configured tenant/person's request is not this Taylor's work.
            detail = self._detail(uow, state.review.review_id)
            if detail.is_current and detail.review.status is FinanceReviewStatus.PENDING:
                results.append(detail)
        return tuple(results)
```

Private `_detail` is called only after authenticated public entry points. A detail lookup returns the requested review's own latest historical revision and immutable selected analysis/option, with `is_current=False` when superseded; it never returns a different current case review. `current_token` is informational for historical detail and cannot authorize resolving it. A race can make read tokens stale; callers retry status/detail in a later request. Do not swallow integrity errors or turn unreadable history into another review.

### B3: Read-model acceptance

- [ ] Add the following concrete tests to the existing service test module; they call real Task A services and reuse its fixture helpers:

```python
def test_pending_list_and_exact_historical_detail(ctx):
    first = ctx.service.submit(submission(ctx), ctx.alex)
    listed = ctx.service.list_pending(ctx.taylor)
    assert [d.review.review_id for d in listed] == [first.review.review_id]
    assert listed[0].is_current
    ctx.service.resolve(resolution(ctx), ctx.taylor)
    assert ctx.service.list_pending(ctx.taylor) == ()
    second = ctx.service.submit(submission(ctx, key='submit-2'), ctx.alex)
    assert [d.review.review_id for d in ctx.service.list_pending(ctx.taylor)] == [second.review.review_id]
    historical = ctx.service.detail(first.review.review_id, ctx.taylor)
    assert historical.review.review_id == first.review.review_id
    assert historical.selection == first.selection
    assert historical.option.option_id == first.selection.proposal.option_id
    assert historical.analysis.analysis_id == first.selection.proposal.analysis_id
    assert historical.review.reason == 'Budget 10000'
    assert historical.review.status.value == 'superseded'
    assert not historical.is_current
    assert historical.current_token.selection_id == second.selection.selection_id

def test_current_status_after_low_cost_selection_is_read_only(ctx):
    ctx.service.submit(submission(ctx), ctx.alex)
    ctx.service.resolve(resolution(ctx), ctx.taylor)
    transfer = ctx.service.submit(submission(ctx, 'RL-OPTION-TRANSFER', 'transfer'), ctx.alex)
    before_state, before_rows = current(ctx), rows(ctx)
    assert ctx.service.status(ctx.case.case_id, ctx.alex).selection == transfer.selection
    assert ctx.service.list_pending(ctx.taylor) == ()
    assert current(ctx) == before_state
    assert rows(ctx) == before_rows

def test_query_authorization_precedes_data_access(ctx):
    def no_database():
        raise AssertionError('unauthorized query opened a UoW')
    service = FinanceService(no_database, actors=ctx.actors)
    with pytest.raises(FinancePermissionDenied):
        service.list_pending(ctx.alex)
    with pytest.raises(FinancePermissionDenied):
        service.detail('known-review-id', ctx.alex)
    with pytest.raises(FinancePermissionDenied):
        service.status(ctx.case.case_id, ctx.taylor)

def test_queries_survive_store_reopen(ctx):
    result = ctx.service.submit(submission(ctx), ctx.alex)
    expected = ctx.service.detail(result.review.review_id, ctx.taylor)
    from services.persistence.sqlite import SqliteStore, build_sqlite_engine
    url = str(ctx.store.engine.url)
    ctx.store.engine.dispose()
    reopened = SqliteStore(build_sqlite_engine(url), runtime_mode=RuntimeMode.FALLBACK)
    try:
        service = FinanceService(reopened.uow_factory, actors=ctx.actors)
        assert service.detail(result.review.review_id, ctx.taylor) == expected
        assert service.list_pending(ctx.taylor) == (expected,)
        assert service.status(ctx.case.case_id, ctx.alex).selection == result.selection
    finally:
        reopened.engine.dispose()
```
- [ ] Verify Alex status/submit and Taylor list/detail/resolve permissions; Taylor status is deliberately accessed through authorized detail/list, not Alex's case endpoint. Use forbidden-UoW factories for denied public reads to prove auth-before-any-data.
- [ ] High-cost pending appears once. Approve/reject removes it. Rejected→new high-cost request lists only new ID. Rejected→transfer lists none. Historical detail of old ID retains original analysis, option and rejection reason, reports superseded/not-current, and never contains the new review ID.
- [ ] Seed another valid tenant's new-workflow Case/selection through persistence with its own valid identities; exact configured Taylor's list excludes it. Detail by its known ID denies access rather than returning its data. Correct tenant but different Alex object is also excluded. Extra/missing-role/unbound actor cannot read/replay.
- [ ] Reopen the file store and construct a new service; status/history/list agree with durable rows. A read-only request creates no rows/side effects and does not change generation. Test current pointer and latest terminal status separately so querying only historical `pending` rows cannot pass.
- [ ] Run `uv run pytest tests/finance tests/integration/test_store_contract.py -q -m 'not fabric_live'`; scoped commit `feat: add authenticated Finance review queries`, then independent review/fix/re-review before acceptance.

## Parent review decisions and remaining limits

1. Submit result is original selection plus immutable pending revision 1; resolution result is original terminal revision. Current status is deliberately separate, satisfying durable retry semantics without persisting another result table.
2. Parent approved command fingerprints excluding mutable display/principal names and including normalized exact authority identity, command expected token/revision, action and reason. Existing Decision fingerprints do not change. Add the UUID-spelling replay test below so normalized principal identity is observable.
3. Pending query fetches only candidate IDs with current pointer/latest pending status; exact tenant/object filtering is done on validated immutable identity snapshots. This avoids a schema addition or database-specific JSON extraction.
4. One case's list/detail may change during a read, yielding `StaleProposal`; HTTP retry/error mapping is the next API plan, not a hidden loop here. No claim of a global snapshot of every pending case is made.
5. Task A and Task B are independently reviewable but both must pass before API composition. Actual Entra sign-ins, HTTP authorization matrix, final Decision enforcement and native Fabric concurrency remain later gates. No runtime activation occurs here.

```python
def test_equivalent_uuid_spelling_replays_original_snapshot(ctx):
    from uuid import UUID
    command = submission(ctx)
    first = ctx.service.submit(command, ctx.alex)
    equivalent = ctx.alex.model_copy(update={
        'tenant_id': UUID(ctx.alex.tenant_id).hex,
        'object_id': UUID(ctx.alex.object_id).hex,
        'user_principal_name': 'renewed-session@example.invalid',
    })
    replay = FinanceService(ctx.store.uow_factory, actors=ctx.actors, clock=no_clock)
    assert replay.submit(command, equivalent) == first
    assert first.selection.submitted_by == ctx.alex

def test_wrong_object_cannot_replay_existing_request(ctx):
    command = submission(ctx)
    ctx.service.submit(command, ctx.alex)
    wrong = ctx.alex.model_copy(update={'object_id': '55555555-5555-4555-8555-555555555555'})
    with pytest.raises(FinancePermissionDenied):
        ctx.service.submit(command, wrong)
```

Planning checks: all nine Python blocks parse; the exact-identity implementation passed a read-only UUID spelling normalization probe against existing IdentitySnapshot types. Full service behavior awaits the accepted selection implementation and the red/green/review cycles above. No service has been activated or deployed by this draft.
