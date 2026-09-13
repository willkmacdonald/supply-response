# Explicit Finance Policy and Legacy Canonical Preservation Implementation Plan

Parent-reviewed September 13, 2026. Legacy baseline captured from 0f23db5 before any policy-model changes; use `.superpowers/sdd/finance-legacy-baseline.patch` without regeneration. This plan implements the already-approved independent Finance workflow in an opt-in compatibility increment.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit independent-Finance case policy while preserving legacy canonical Case, Analysis, nested ApprovalTarget and Decision JSON exactly.

**Architecture:** A nullable immutable Case discriminator defaults to legacy and is omitted only when absent. Analysis policy derives from that discriminator and filters Finance standing authorizations only for the new version. Persistence rejects case/projection/analysis version disagreement; existing creation routes remain legacy.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy Core, Alembic, SQLite, pytest.

## Global constraints

- This is the compatibility and policy increment of the approved Finance workflow. No routes, live composition, Finance services, Decision enforcement or activation.
- No table changes; no new migration is needed. The accepted predecessor migration is `0007_finance_review_revisions`. Wait for that task to land before running the migration fixture test.
- Freeze full raw JSON before model changes. Never regenerate it to make a regression pass. Do not save binary database fixtures.
- Keep `APPROVAL_POLICY_VERSION = 'standing-authorization-v1'` as the public legacy constant. Derive the actual output per Case.
- Do not add fields to `AnalysisMaterial`, `Decision`, or `ApprovalTarget`; the nested Case serializer is the only change affecting those models.
- Do not change `serialize_model`, global `FrozenModel` configuration or global omission settings. Existing explicit JSON nulls remain nulls.
- Runtime fallback data is a deterministic test fixture, not evidence of actual Taylor review.
- All test commands use `-m 'not fabric_live'`; no live calls or schema application.

## Files

- Modify `data/domain/cases.py`: `WorkflowVersion`, optional discriminator, property, targeted serializer and validated-copy immutability.
- Create `services/policy/workflow.py`: version mapping and Finance standing filtering.
- Modify `services/analysis/service.py`: optional policy assertion, derivation, filtered canonical input and actual output policy.
- Modify `data/synthetic/rl001.py`: explicit opt-in fixture construction parameter; default remains `None`.
- Modify `services/persistence/store.py`: policy provenance checks in existing validation methods.
- Create `tests/finance/fixtures/legacy-policy.json`: frozen full raw payloads and material hash.
- Create `tests/finance/test_workflow_policy.py`: all tests below, isolated temporary database only.

## Task 2: One reviewable compatibility and policy change

### Step 1: Freeze the committed legacy pipeline before editing models

- [ ] Confirm predecessor storage review is accepted and the worktree is clean for the production files listed above. Existing unrelated changes are not part of this task.
- [ ] Run the following read-only generator from the worktree root. It uses current deterministic domain helpers and a temporary SQLite database, patches the Decision UUID only in this process, fixes server time, and prints an exact `apply_patch` input. Apply the printed patch with `apply_patch`; do not redirect shell output into the fixture file. The command intentionally imports no new policy symbols, so it runs before implementation.

```bash
uv run python - <<'PY'
import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

from data.domain import CasePurpose, CaseStatus, RuntimeMode
from data.domain.decisions import CorpusScope, DecisionKind, IdentitySnapshot, RecordDecisionCommand, StandingAuthorization
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import instantiate_rl001, build_rl001_evidence
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService
from services.persistence.sqlite import sqlite_store
from services.persistence.store import serialize_model

case, snapshot = instantiate_rl001(
    case_id='RL-CASE-LEGACY-FINANCE-COMPAT',
    purpose=CasePurpose.AUTOMATED_TEST, runtime_mode=RuntimeMode.FALLBACK,
)
started = datetime.fromisoformat('2026-09-01T09:01:00-05:00')
analysis = analyze_case(AnalyzeCaseCommand(
    analysis_id='RL-ANALYSIS-LEGACY-FINANCE-COMPAT', case=case,
    corpus=CorpusScope.DEMO_CORPUS, operational_snapshot=snapshot,
    evidence_items=build_rl001_evidence(snapshot,
        analysis_id='RL-ANALYSIS-LEGACY-FINANCE-COMPAT', retrieved_at=started),
    standing_authorizations=(StandingAuthorization.taylor_rl001(),),
    analysis_started_at=started, created_at=started,
    calculation_version='rl001-options-v1',
))
actor = IdentitySnapshot(
    persona_id='RL-PERSONA-ALEX',
    effective_roles=('material_planner', 'response_approver'),
    identity_source=IdentitySource.ENTRA, source_id='RL-ENTRA-ALEX',
    display_name='Alex Morgan', user_principal_name='alex@example.invalid',
)
command = RecordDecisionCommand(
    case_id=case.case_id, analysis_id=analysis.analysis_id,
    selected_option_id='RL-OPTION-COMBINED', kind=DecisionKind.APPROVED,
    idempotency_key='RL-IDEMPOTENCY-LEGACY-FINANCE-COMPAT',
)
with TemporaryDirectory(prefix='finance-policy-baseline-') as directory:
    store = sqlite_store(f'sqlite:///{Path(directory) / "baseline.db"}')
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    store.save_case_projection(case.model_copy(update={'status': CaseStatus.AWAITING_DECISION}))
    with patch('data.domain.decisions.uuid4', return_value=UUID('44444444-4444-4444-8444-444444444444')):
        decision = DecisionService(store.uow_factory,
            clock=lambda: datetime.fromisoformat('2026-09-01T14:02:00+00:00')).record(command, actor)
    projected_case = store.get_projection(case.case_id).case
    store.engine.dispose()
target = next(s.target for s in decision.approval_satisfactions if s.role == 'finance_approver')
assert target.case.case_id == case.case_id
assert any(s.role == 'material_planner' for s in decision.approval_satisfactions)
payload = {
    'case': serialize_model(case), 'snapshot': serialize_model(snapshot),
    'analysis': serialize_model(analysis), 'target': serialize_model(target),
    'decision': serialize_model(decision), 'projected_case': serialize_model(projected_case),
    'command': serialize_model(command), 'analysis_material_hash': analysis.material_hash,
}
print('*** Begin Patch')
print('*** Add File: tests/finance/fixtures/legacy-policy.json')
for line in json.dumps(payload, indent=2, ensure_ascii=False).splitlines():
    print('+' + line)
print('*** End Patch')
PY
```

The JSON fixture contains complete canonical strings, including both Taylor and Alex satisfaction targets and all Decision metadata. Outer JSON indentation is incidental; compare the inner raw strings byte-for-byte.

### Step 2: Add the concrete regression tests

- [ ] Create `tests/finance/test_workflow_policy.py` with the following imports/helpers/tests. The initial missing `WorkflowVersion` import is the expected RED condition.

```python
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
from data.domain.decisions import ApprovalTarget, Decision, CorpusScope, StandingAuthorization
from data.domain.execution import ActionPlanningRequested
from data.synthetic.rl001 import OperationalSnapshot, instantiate_rl001, build_rl001_evidence
from services.analysis.service import AnalyzeCaseCommand, analyze_case, analysis_material_hash
from services.persistence.sqlite import SqliteStore, build_sqlite_engine, sqlite_store
from services.persistence.store import PersistenceIntegrityError, serialize_model
from services.persistence.tables import case_instances, case_projection, analysis_versions, decisions
from services.policy.evidence import PolicyViolation

FIXTURE = Path(__file__).parent / 'fixtures' / 'legacy-policy.json'

@pytest.fixture
def raw():
    return json.loads(FIXTURE.read_text())

def build(version=None):
    case, snapshot = instantiate_rl001(
        case_id='RL-CASE-POLICY', purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK, workflow_version=version,
    )
    started = datetime.fromisoformat('2026-09-01T09:01:00-05:00')
    command = AnalyzeCaseCommand(
        analysis_id='RL-ANALYSIS-POLICY', case=case,
        corpus=CorpusScope.DEMO_CORPUS, operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(snapshot,
            analysis_id='RL-ANALYSIS-POLICY', retrieved_at=started),
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=started, created_at=started,
        calculation_version='rl001-options-v1',
    )
    return case, snapshot, command

@pytest.mark.parametrize('name,model', [
    ('case', CaseInstance), ('projected_case', CaseInstance),
    ('analysis', AnalysisVersion), ('target', ApprovalTarget), ('decision', Decision),
])
def test_full_legacy_canonical_roundtrip(raw, name, model):
    assert serialize_model(model.model_validate_json(raw[name])) == raw[name]

def test_legacy_hash_and_nested_nulls_remain(raw):
    analysis = AnalysisVersion.model_validate_json(raw['analysis'])
    assert analysis_material_hash(analysis.material) == raw['analysis_material_hash']
    decision = Decision.model_validate_json(raw['decision'])
    encoded = json.loads(serialize_model(decision))
    assert encoded['rejection_reason'] is None
    assert encoded['actor']['tenant_id'] is None
    for satisfaction in encoded['approval_satisfactions']:
        assert 'workflow_version' not in satisfaction['target']['case']

def test_status_copy_does_not_add_legacy_field(raw):
    case = CaseInstance.model_validate_json(raw['case'])
    changed = case.model_copy(update={'status': CaseStatus.ACTION_PLANNING})
    expected = json.loads(raw['case'])
    expected['status'] = CaseStatus.ACTION_PLANNING.value
    assert json.loads(serialize_model(changed)) == expected
    assert 'workflow_version' not in changed.model_dump()
    assert changed.effective_workflow_version is WorkflowVersion.LEGACY

def test_case_version_is_explicit_and_immutable():
    legacy, _, _ = build()
    with pytest.raises(ValueError, match='workflow_version changes require'):
        legacy.model_copy(update={'workflow_version': WorkflowVersion.INDEPENDENT_FINANCE})
    changed = legacy.model_copy(update={
        'case_id': 'RL-CASE-DIFFERENT',
        'workflow_version': WorkflowVersion.INDEPENDENT_FINANCE,
    })
    assert json.loads(serialize_model(changed))['workflow_version'] == 'independent-finance-v1'
    assert changed.model_copy(update={'status': CaseStatus.AWAITING_DECISION}).effective_workflow_version is WorkflowVersion.INDEPENDENT_FINANCE

@pytest.mark.parametrize('version,expected,finance', [
    (None, 'standing-authorization-v1', True),
    (WorkflowVersion.INDEPENDENT_FINANCE, 'independent-finance-v1', False),
])
def test_policy_derives_from_case(version, expected, finance):
    case, snapshot, command = build(version)
    result = analyze_case(command)
    assert result.material.approval_policy_version == expected
    assert any(s.role == 'finance_approver' for s in result.approval_satisfactions) is finance
    assert any(s.role == 'finance_approver' for s in result.material.standing_authorizations) is finance
    combined = next(o for o in result.response_options if o.option_id == 'RL-OPTION-COMBINED')
    assert combined.executable
    assert 'finance_approver' in combined.prerequisite_roles
    explicit = analyze_case(command.model_copy(update={'approval_policy_version': expected}))
    assert serialize_model(explicit) == serialize_model(result)

@pytest.mark.parametrize('version,asserted', [
    (None, 'independent-finance-v1'),
    (WorkflowVersion.INDEPENDENT_FINANCE, 'standing-authorization-v1'),
    (None, 'RL-FORGED-APPROVAL-POLICY'),
])
def test_explicit_wrong_policy_is_rejected(version, asserted):
    _, _, command = build(version)
    with pytest.raises(PolicyViolation, match='Approval policy version'):
        analyze_case(command.model_copy(update={'approval_policy_version': asserted}))

def test_projection_cannot_change_immutable_case_policy(tmp_path):
    case, snapshot, _ = build()
    store = sqlite_store(f'sqlite:///{tmp_path / "projection.db"}')
    store.create_case(case, snapshot)
    forged = CaseInstance.model_validate({
        **case.model_dump(), 'workflow_version': WorkflowVersion.INDEPENDENT_FINANCE,
    })
    with pytest.raises(PersistenceIntegrityError):
        store.save_case_projection(forged)
    assert store.get_case(case.case_id).effective_workflow_version is WorkflowVersion.LEGACY
    with store.engine.begin() as connection:
        connection.execute(update(case_projection).where(
            case_projection.c.case_id == case.case_id
        ).values(payload_json=serialize_model(forged)))
    with pytest.raises(PersistenceIntegrityError):
        store.get_projection(case.case_id)
    store.engine.dispose()

@pytest.mark.parametrize('stored_version,analysis_version', [
    (WorkflowVersion.INDEPENDENT_FINANCE, None),
    (None, WorkflowVersion.INDEPENDENT_FINANCE),
])
def test_persistence_rejects_cross_policy_analysis(tmp_path, stored_version, analysis_version):
    stored, snapshot, _ = build(stored_version)
    _, _, command = build(analysis_version)
    store = sqlite_store(f'sqlite:///{tmp_path / "lineage.db"}')
    store.create_case(stored, snapshot)
    with pytest.raises(PersistenceIntegrityError, match='approval policy'):
        store.save_analysis(analyze_case(command))
    with store.engine.connect() as connection:
        assert connection.execute(select(analysis_versions)).all() == []
    store.engine.dispose()

def test_frozen_legacy_rows_read_from_migrated_0007_database(tmp_path, raw):
    url = f'sqlite:///{tmp_path / "legacy.db"}'
    config = Config('migrations/alembic.ini')
    config.set_main_option('sqlalchemy.url', url)
    alembic_command.upgrade(config, '0007_finance_review_revisions')
    # Deliberately avoid sqlite_store/create_all: migration alone creates schema.
    engine = build_sqlite_engine(url)
    store = SqliteStore(engine, runtime_mode=RuntimeMode.FALLBACK)
    case = CaseInstance.model_validate_json(raw['case'])
    snapshot = OperationalSnapshot.model_validate_json(raw['snapshot'])
    analysis = AnalysisVersion.model_validate_json(raw['analysis'])
    decision = Decision.model_validate_json(raw['decision'])
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    with store.uow_factory() as uow:
        uow.decisions.insert(decision)
        uow.decisions.insert_satisfactions(decision.decision_id, decision.approval_satisfactions)
        uow.execution.insert_outbox(ActionPlanningRequested.for_decision(decision))
        uow.cases.set_current_decision(case.case_id, decision.decision_id)
        uow.commit()
    with engine.connect() as connection:
        before = tuple(connection.scalar(select(table.c.payload_json))
            for table in (case_instances, analysis_versions, decisions))
    assert before == (raw['case'], raw['analysis'], raw['decision'])
    # Reopen, proving reads from persisted raw JSON, not object reuse.
    engine.dispose()
    engine = build_sqlite_engine(url)
    store = SqliteStore(engine, runtime_mode=RuntimeMode.FALLBACK)
    # get_case reads the mutable projection; immutable Case bytes were checked above.
    assert serialize_model(store.get_case(case.case_id)) == raw['projected_case']
    assert serialize_model(store.get_analysis(analysis.analysis_id)) == raw['analysis']
    with store.uow_factory() as uow:
        assert serialize_model(uow.decisions.get(decision.decision_id)) == raw['decision']
    with engine.connect() as connection:
        after = tuple(connection.scalar(select(table.c.payload_json))
            for table in (case_instances, analysis_versions, decisions))
    assert after == before
    assert analysis_material_hash(store.get_analysis(analysis.analysis_id).material) == raw['analysis_material_hash']
    engine.dispose()
```

- [ ] Run `uv run pytest tests/finance/test_workflow_policy.py -q -m 'not fabric_live'`. Expected RED: new enum import absent. After introducing enum, missing opt-in signature and policy behavior expose subsequent failures; do not weaken tests to preserve green between partial edits.

### Step 3: Implement Case policy without broad serialization changes

- [ ] In `data/domain/cases.py`, add `from pydantic import SerializerFunctionWrapHandler, model_serializer`. Add this enum before `CaseInstance`:

```python
class WorkflowVersion(StrEnum):
    LEGACY = 'standing-authorization-v1'
    INDEPENDENT_FINANCE = 'independent-finance-v1'
```

- [ ] Append the following field/methods to `CaseInstance` before `model_copy`:

```python
workflow_version: WorkflowVersion | None = None

@property
def effective_workflow_version(self) -> WorkflowVersion:
    return self.workflow_version or WorkflowVersion.LEGACY

@model_serializer(mode='wrap')
def serialize_case(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
    payload = handler(self)
    if self.workflow_version is None:
        payload.pop('workflow_version', None)
    return payload
```

- [ ] Keep existing `model_copy` revalidation and runtime-mode rule exactly. Immediately before `return changed`, add:

```python
if (
    changed.effective_workflow_version != self.effective_workflow_version
    and changed.case_id == self.case_id
):
    raise ValueError('workflow_version changes require a different case_id')
```

`None` and explicit legacy have the same effective policy; immutable persisted canonical Case payload still cannot be overwritten with another representation. New-version status copies retain their explicit field. Do not export the enum through the broad domain index merely for convenience; new callers import from `data.domain.cases`.

- [ ] In `data/synthetic/rl001.py`, import `WorkflowVersion` from `data.domain.cases`. Replace the function signature with:

```python
def instantiate_rl001(
    *, case_id: str, purpose: CasePurpose, runtime_mode: RuntimeMode,
    workflow_version: WorkflowVersion | None = None,
) -> tuple[CaseInstance, OperationalSnapshot]:
```

Add `workflow_version=workflow_version` to its `CaseInstance(...)` construction. Leave snapshot construction and all callers unchanged.

### Step 4: Derive analysis policy and preserve the legacy computation

- [ ] Create `services/policy/workflow.py` with this complete content:

```python
from data.domain.cases import CaseInstance, WorkflowVersion
from data.domain.decisions import StandingAuthorization


def approval_policy_for(case: CaseInstance) -> str:
    return case.effective_workflow_version.value


def standing_authorizations_for(
    case: CaseInstance,
    authorizations: tuple[StandingAuthorization, ...],
) -> tuple[StandingAuthorization, ...]:
    if case.effective_workflow_version is WorkflowVersion.LEGACY:
        return authorizations
    return tuple(item for item in authorizations if item.role != 'finance_approver')
```

- [ ] Import these functions in `services/analysis/service.py`. Change only the `AnalyzeCaseCommand.approval_policy_version` field and `create_analysis_version` keyword parameter to `str | None = None`. Keep constant `APPROVAL_POLICY_VERSION` unchanged. Replace the current equality check with:

```python
effective_approval_policy = approval_policy_for(case)
if approval_policy_version is not None and approval_policy_version != effective_approval_policy:
    raise PolicyViolation('Approval policy version does not match the evaluator.')
```

- [ ] Keep duplicate input authorization validation in place. Replace construction of `canonical_authorizations` with:

```python
canonical_authorizations = tuple(sorted(
    standing_authorizations_for(case, standing_authorizations),
    key=lambda item: item.authorization_id,
))
```

This filters Finance before both satisfaction evaluation and immutable authorization material construction; quality policy remains unchanged. Replace `approval_policy_version=APPROVAL_POLICY_VERSION` in `AnalysisMaterial(...)` with `approval_policy_version=effective_approval_policy`. `analyze_case` already forwards the command field, so its forwarding remains unchanged. Both public construction paths now reject explicit policy mismatch and derive when omitted.

### Step 5: Enforce immutable provenance in persistence

- [ ] Import `WorkflowVersion` from `data.domain.cases` and `approval_policy_for` from `services.policy.workflow` into `services/persistence/store.py` (extend existing imports rather than duplicate).
- [ ] In `_require_case_projection_integrity` add this OR clause alongside existing immutable Case comparisons:

```python
or case.effective_workflow_version is not stored_case.effective_workflow_version
```

- [ ] In `_require_analysis_provenance`, immediately after `material = analysis.material`, add:

```python
if material.approval_policy_version != approval_policy_for(stored_case):
    raise PersistenceIntegrityError(
        'Analysis approval policy must match its immutable Case Instance'
    )
if stored_case.effective_workflow_version is WorkflowVersion.INDEPENDENT_FINANCE:
    if (
        any(item.role == 'finance_approver' for item in material.standing_authorizations)
        or any(item.role == 'finance_approver' for item in material.approval_satisfactions)
        or any(item.role == 'finance_approver' for item in analysis.approval_satisfactions)
    ):
        raise PersistenceIntegrityError(
            'Independent Finance approval policy cannot contain Finance standing evidence'
        )
```

- [ ] In the existing loop `for item in analysis.approval_satisfactions`, after `target_case = item.target.case`, add:

```python
if target_case.effective_workflow_version is not stored_case.effective_workflow_version:
    raise PersistenceIntegrityError(
        'Approval Satisfaction case policy must match its immutable Case Instance'
    )
```

These guards protect direct store callers as well as analysis construction. Existing save/get paths already call `_require_analysis_provenance`; keep that connection-local validation. No route defaults, runtime actor bindings, reporting schema or metadata changes.

### Step 6: Complete negative policy checks and verify

- [ ] Add these two tests to the same test module; they protect repository bypass attempts beyond the normal construction path:

```python
def test_new_policy_rejects_injected_legacy_finance_material(tmp_path):
    case, snapshot, _ = build(WorkflowVersion.INDEPENDENT_FINANCE)
    _, _, legacy_command = build()
    legacy = analyze_case(legacy_command)
    forged_material = legacy.material.model_copy(update={
        'approval_policy_version': 'independent-finance-v1',
    })
    forged = legacy.model_copy(update={
        'material': forged_material,
        'material_hash': analysis_material_hash(forged_material),
    })
    store = sqlite_store(f'sqlite:///{tmp_path / "injected.db"}')
    store.create_case(case, snapshot)
    with pytest.raises(PersistenceIntegrityError, match='Finance standing evidence'):
        store.save_analysis(forged)
    store.engine.dispose()

def test_legacy_baseline_rebuild_still_matches_frozen_analysis(raw):
    case = CaseInstance.model_validate_json(raw['case'])
    snapshot = OperationalSnapshot.model_validate_json(raw['snapshot'])
    started = datetime.fromisoformat('2026-09-01T09:01:00-05:00')
    result = analyze_case(AnalyzeCaseCommand(
        analysis_id='RL-ANALYSIS-LEGACY-FINANCE-COMPAT', case=case,
        corpus=CorpusScope.DEMO_CORPUS, operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(snapshot,
            analysis_id='RL-ANALYSIS-LEGACY-FINANCE-COMPAT', retrieved_at=started),
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=started, created_at=started,
        calculation_version='rl001-options-v1',
    ))
    assert serialize_model(result) == raw['analysis']
    assert result.material_hash == raw['analysis_material_hash']
```

- [ ] Run `uv run pytest tests/finance/test_workflow_policy.py -q -m 'not fabric_live'`. Expected GREEN: every parameterized compatibility, policy and persistence case passes.
- [ ] Run `uv run pytest tests/analysis tests/domain/test_rl001_contract.py tests/domain/test_finance_review.py tests/persistence/test_decision_outbox.py tests/persistence/test_sqlite_store.py tests/api/test_case_lifecycle.py tests/api/test_failure_contracts.py tests/integration/test_store_contract.py -q -m 'not fabric_live'`. Existing route-created cases must still produce legacy policy and existing standing evidence. No live case contract is invoked.
- [ ] Inspect the diff for only the code/test/fixture paths listed. Confirm no global serializer changes, no route edits, no new database object and no changed golden fixture after implementation. Verify `git diff --check`.
- [ ] Commit the reviewed deliverable with `git add data/domain/cases.py services/policy/workflow.py services/analysis/service.py data/synthetic/rl001.py services/persistence/store.py tests/finance/test_workflow_policy.py tests/finance/fixtures/legacy-policy.json` followed by `git commit -m "feat: add explicit independent Finance case policy"`.

## Review and acceptance boundary

Accept this task only if full legacy JSON reconstruction and actual analysis recomputation match the frozen baseline, status copies preserve shape, direct persistence cannot mix policies, and migrated 0007 reads leave raw rows unchanged. The temporary database is created in pytest; no binary artifact is committed.

New-version analyses deliberately retain Finance prerequisite roles and feasible options while omitting Taylor standing evidence. Final Decision services do not yet consume new-version review evidence; that is a later independently reviewed task. Existing production creation routes remain legacy until the Finance service and authenticated Taylor API composition are complete.
