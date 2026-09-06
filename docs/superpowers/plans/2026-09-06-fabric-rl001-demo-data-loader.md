# Fabric RL-001 Demo Data Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the frozen fictional RL-001 operational bundle into Fabric SQL through a guarded, idempotent command and let live analysis reuse it on any presentation date.

**Architecture:** Keep authoritative demo-payload construction and insert-only persistence in a focused Fabric integration module. A thin CLI validates the live Azure CLI environment, defaults to a non-mutating plan, and verifies an applied row through `FabricLiveOperationalDataPort`. Live boundary validation will use wall clock only for current retrieval and leave business validity to the existing Scenario Effective Time policy.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy 2, pyodbc, Azure Identity, pytest, Microsoft Fabric SQL Database

## Global Constraints

- The canonical Scenario Effective Time remains `2026-09-01T09:00:00-05:00` in `America/Chicago`.
- The stable source snapshot ID is `RL-001-OPERATIONAL-V1`; the loader never replaces a different payload under that ID.
- The business scenario remains visibly fictional, while loaded evidence uses `runtime_mode=live`, `source_system=fabric`, and `synthetic=false` to describe its live authority path.
- Dry-run is the default; `--apply` is required for the one permitted insert.
- Repeated exact applies are no-ops; mismatched existing data fails without update or deletion.
- Source/business timestamps are not compared with presentation time. Current retrieval is proven by the existing analysis-bound `retrieved_at` window.
- No access token, credential, connection string, or complete JSON payload is printed or committed.
- Existing Work IQ bindings, Foundry agents, Entra identities, Power BI bindings, fallback behavior, RL-001 calculations, and schema version 12 remain unchanged.

---

### Task 1: Align live evidence time validation with the frozen scenario clock

**Files:**
- Modify: `tests/integration/test_live_hardening.py`
- Modify: `apps/api/app/live.py`

**Interfaces:**
- Consumes: `_validate_live_collection(...)` and `_require_item(...)` live trust-boundary functions; `validate_evidence(...)` remains the business-validity authority.
- Produces: live boundary validation that requires present source metadata and current analysis retrieval but does not expire a fixed scenario corpus based on presentation date.

- [ ] **Step 1: Write the failing fixed-scenario timestamp test**

Add `SCENARIO_EFFECTIVE_TIME` and the private boundary helpers to the imports in `tests/integration/test_live_hardening.py`, then add:

```python
def test_live_boundary_accepts_fixed_scenario_evidence_retrieved_on_a_later_date():
    presentation_time = datetime(2026, 10, 15, 16, 0, tzinfo=UTC)
    item = _evidence(
        evidence_id="RL-ALPHA-OPTIONAL-3000",
        case_id="RL-CASE-LIVE",
        analysis_id="RL-ANALYSIS-LIVE",
        source_system=EvidenceSourceSystem.FABRIC,
        source_id="fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000",
        scope=AuthorityScope.OPERATIONAL_QUANTITY,
        citation="https://app.powerbi.com/groups/demo/reports/report",
        source_timestamp=SCENARIO_EFFECTIVE_TIME,
    ).model_copy(
        update={
            "retrieved_at": presentation_time,
            "effective_at": SCENARIO_EFFECTIVE_TIME,
            "expires_at": SCENARIO_EFFECTIVE_TIME + timedelta(days=1),
        }
    )

    validated = _validate_live_collection(
        (item,),
        system=EvidenceSourceSystem.FABRIC,
        allowed_scopes={AuthorityScope.OPERATIONAL_QUANTITY},
        source_id=None,
        analysis_id="RL-ANALYSIS-LIVE",
        case_id="RL-CASE-LIVE",
        started_at=presentation_time,
        citation_hosts={"app.powerbi.com"},
    )
    _require_item(
        validated,
        system=EvidenceSourceSystem.FABRIC,
        scope=AuthorityScope.OPERATIONAL_QUANTITY,
        source_id=None,
        analysis_id="RL-ANALYSIS-LIVE",
        case_id="RL-CASE-LIVE",
        started_at=presentation_time,
        citation_hosts={"app.powerbi.com"},
    )

    assert validated == (item,)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
uv run pytest tests/integration/test_live_hardening.py::test_live_boundary_accepts_fixed_scenario_evidence_retrieved_on_a_later_date -q
```

Expected: FAIL with `ValueError: live evidence collection contains an invalid item`, because the current boundary compares `source_timestamp` and `expires_at` with wall-clock `started_at`.

- [ ] **Step 3: Remove wall-clock source/business validity checks from the boundary**

In `_require_item`, retain `item.source_timestamp is None` as a missing-metadata failure and delete only:

```python
or abs(started_at - item.source_timestamp) > timedelta(hours=24)
```

In `_validate_live_collection`, retain required non-null timestamps and current `retrieved_at`, but delete only:

```python
or abs(started_at - item.source_timestamp) > timedelta(hours=24)
or (item.expires_at is not None and item.expires_at < started_at)
```

Do not alter `services/policy/evidence.py`; its `_item_validation` already checks timestamp ordering and the five-minute analysis retrieval window against wall clock, then checks `effective_at` and `expires_at` against `scenario_effective_time`.

- [ ] **Step 4: Run the focused and policy tests**

Run:

```bash
uv run pytest tests/integration/test_live_hardening.py::test_live_boundary_accepts_fixed_scenario_evidence_retrieved_on_a_later_date tests/analysis/test_evidence_and_approvals.py -q
```

Expected: PASS; existing tests still prove stale current-analysis retrieval and scenario-expired business evidence are rejected by policy.

- [ ] **Step 5: Commit the time-semantics correction**

```bash
git add apps/api/app/live.py tests/integration/test_live_hardening.py
git commit -m "fix(live): separate retrieval and scenario time"
```

### Task 2: Build and persist the canonical Fabric source bundle

**Files:**
- Create: `integrations/fabric/demo_source.py`
- Create: `tests/integrations/test_fabric_demo_source.py`

**Interfaces:**
- Consumes: `OperationalSnapshot.rl001(case_id: str, runtime_mode: RuntimeMode)`, `EvidenceItem`, `SCENARIO_EFFECTIVE_TIME`, and a SQLAlchemy `Connection`.
- Produces: `LiveOperationalSourceBundle`, `build_rl001_live_source(citation_url: str)`, and `ensure_rl001_live_source(connection: Connection, bundle: LiveOperationalSourceBundle, *, apply: bool) -> Literal["planned", "inserted", "unchanged"]`.

- [ ] **Step 1: Write failing canonical-bundle tests**

Create `tests/integrations/test_fabric_demo_source.py` with:

```python
from datetime import timedelta

import pytest

from data.domain import RuntimeMode
from data.domain.evidence import AuthorityScope, EvidenceSourceSystem
from data.synthetic.rl001 import SCENARIO_EFFECTIVE_TIME
from integrations.fabric.demo_source import (
    build_rl001_live_source,
    ensure_rl001_live_source,
)


class _MappingsResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one_or_none(self):
        return self._row


class FakeConnection:
    def __init__(self, row=None):
        self.row = row
        self.inserts = []

    def execute(self, statement, parameters=None):
        sql = str(statement).strip().upper()
        if sql.startswith("SELECT"):
            return _MappingsResult(self.row)
        if sql.startswith("INSERT"):
            self.inserts.append(dict(parameters or {}))
            return _MappingsResult(None)
        raise AssertionError(f"Unexpected SQL: {sql}")


def _row(bundle):
    return {
        "source_snapshot_id": bundle.source_snapshot_id,
        "template_id": bundle.template_id,
        "effective_at": bundle.effective_at,
        "is_verified": bundle.is_verified,
        "snapshot_payload_json": bundle.snapshot_payload_json,
        "evidence_payload_json": bundle.evidence_payload_json,
    }


def test_builds_the_exact_live_fabric_rl001_bundle():
    bundle = build_rl001_live_source(
        "https://app.powerbi.com/groups/demo/reports/report"
    )

    assert bundle.source_snapshot_id == "RL-001-OPERATIONAL-V1"
    assert bundle.template_id == "RL-001"
    assert bundle.effective_at == SCENARIO_EFFECTIVE_TIME
    assert bundle.is_verified is True
    snapshot = bundle.snapshot()
    assert snapshot.runtime_mode is RuntimeMode.LIVE
    assert snapshot.scenario_effective_time == SCENARIO_EFFECTIVE_TIME
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-CHI") == 4000
    assert snapshot.usable_inventory("RL-MAT-10247", "RL-PLANT-DAL") == 1500
    evidence = bundle.evidence()
    assert {item.evidence_id for item in evidence} == {
        "RL-ALPHA-OPTIONAL-3000",
        "RL-TRANSFER-DAL-CHI-1500",
        "RL-QUALITY-001",
    }
    assert all(item.source_system is EvidenceSourceSystem.FABRIC for item in evidence)
    assert all(item.runtime_mode is RuntimeMode.LIVE for item in evidence)
    assert all(item.synthetic is False for item in evidence)
    assert all(item.source_timestamp == SCENARIO_EFFECTIVE_TIME for item in evidence)
    assert all(item.effective_at == SCENARIO_EFFECTIVE_TIME for item in evidence)
    assert all(item.expires_at == SCENARIO_EFFECTIVE_TIME + timedelta(days=1) for item in evidence)
    scopes = {scope for item in evidence for scope in item.authority_scope}
    assert scopes == {
        AuthorityScope.OPERATIONAL_QUANTITY,
        AuthorityScope.OPERATIONAL_DATE,
        AuthorityScope.QUALIFICATION_STATE,
    }


def test_dry_run_plans_without_inserting():
    bundle = build_rl001_live_source("https://app.powerbi.com/groups/demo/reports/report")
    connection = FakeConnection()

    assert ensure_rl001_live_source(connection, bundle, apply=False) == "planned"
    assert connection.inserts == []


def test_apply_inserts_once_and_exact_repeat_is_unchanged():
    bundle = build_rl001_live_source("https://app.powerbi.com/groups/demo/reports/report")
    connection = FakeConnection()

    assert ensure_rl001_live_source(connection, bundle, apply=True) == "inserted"
    assert connection.inserts == [_row(bundle)]
    connection.row = _row(bundle)
    assert ensure_rl001_live_source(connection, bundle, apply=True) == "unchanged"
    assert connection.inserts == [_row(bundle)]


def test_mismatched_existing_source_fails_without_mutation():
    bundle = build_rl001_live_source("https://app.powerbi.com/groups/demo/reports/report")
    existing = _row(bundle)
    existing["snapshot_payload_json"] = "{}"
    connection = FakeConnection(existing)

    with pytest.raises(RuntimeError, match="differs from the canonical bundle"):
        ensure_rl001_live_source(connection, bundle, apply=True)

    assert connection.inserts == []
```

- [ ] **Step 2: Run the new test module to verify it fails**

Run:

```bash
uv run pytest tests/integrations/test_fabric_demo_source.py -q
```

Expected: collection ERROR with `ModuleNotFoundError: No module named 'integrations.fabric.demo_source'`.

- [ ] **Step 3: Implement the typed bundle builder and insert-only persistence**

Create `integrations/fabric/demo_source.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Mapping

from sqlalchemy import Connection, text

from apps.api.app.live import validate_live_https_url
from data.domain import RuntimeMode
from data.domain.evidence import (
    AuthorityScope,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    RetrievalHealth,
    UncertaintyState,
)
from data.synthetic.rl001 import OperationalSnapshot, SCENARIO_EFFECTIVE_TIME


SOURCE_SNAPSHOT_ID = "RL-001-OPERATIONAL-V1"
TEMPLATE_CASE_ID = "RL-CASE-TEMPLATE"
TEMPLATE_ANALYSIS_ID = "RL-ANALYSIS-TEMPLATE"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class LiveOperationalSourceBundle:
    source_snapshot_id: str
    template_id: str
    effective_at: datetime
    is_verified: bool
    snapshot_payload_json: str
    evidence_payload_json: str

    def snapshot(self) -> OperationalSnapshot:
        return OperationalSnapshot.model_validate_json(self.snapshot_payload_json)

    def evidence(self) -> tuple[EvidenceItem, ...]:
        values = json.loads(self.evidence_payload_json)
        return tuple(EvidenceItem.model_validate(value) for value in values)

    def parameters(self) -> dict[str, object]:
        return {
            "source_snapshot_id": self.source_snapshot_id,
            "template_id": self.template_id,
            "effective_at": self.effective_at,
            "is_verified": self.is_verified,
            "snapshot_payload_json": self.snapshot_payload_json,
            "evidence_payload_json": self.evidence_payload_json,
        }


def _fabric_evidence(
    *,
    evidence_id: str,
    source_id: str,
    authority_scope: tuple[AuthorityScope, ...],
    claim: str,
    citation_url: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        case_id=TEMPLATE_CASE_ID,
        kind=EvidenceKind.OPERATIONAL_FACT,
        authority_scope=authority_scope,
        source_system=EvidenceSourceSystem.FABRIC,
        source_id=source_id,
        source_timestamp=SCENARIO_EFFECTIVE_TIME,
        retrieved_at=SCENARIO_EFFECTIVE_TIME,
        retrieved_for_analysis_id=TEMPLATE_ANALYSIS_ID,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=SCENARIO_EFFECTIVE_TIME,
        expires_at=SCENARIO_EFFECTIVE_TIME + timedelta(days=1),
        claim=claim,
        excerpt=claim,
        citation_url=citation_url,
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
        requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
        uncertainty_state=UncertaintyState.CERTAIN,
    )


def build_rl001_live_source(citation_url: str) -> LiveOperationalSourceBundle:
    trusted_citation = validate_live_https_url(
        citation_url, allowed_hosts={"app.powerbi.com"}
    )
    snapshot = OperationalSnapshot.rl001(
        case_id=TEMPLATE_CASE_ID,
        runtime_mode=RuntimeMode.LIVE,
    )
    evidence = (
        _fabric_evidence(
            evidence_id="RL-ALPHA-OPTIONAL-3000",
            source_id="fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000",
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
            ),
            claim="Alpha partial shipment quantity and date are confirmed.",
            citation_url=trusted_citation,
        ),
        _fabric_evidence(
            evidence_id="RL-TRANSFER-DAL-CHI-1500",
            source_id="fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500",
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
            ),
            claim="Dallas transfer quantity and date are confirmed.",
            citation_url=trusted_citation,
        ),
        _fabric_evidence(
            evidence_id="RL-QUALITY-001",
            source_id="fabric.qualification/RL-QUAL-BETA",
            authority_scope=(AuthorityScope.QUALIFICATION_STATE,),
            claim="Beta qualification state is pending.",
            citation_url=trusted_citation,
        ),
    )
    return LiveOperationalSourceBundle(
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
        template_id="RL-001",
        effective_at=SCENARIO_EFFECTIVE_TIME,
        is_verified=True,
        snapshot_payload_json=_canonical_json(snapshot.model_dump(mode="json")),
        evidence_payload_json=_canonical_json(
            [item.model_dump(mode="json") for item in evidence]
        ),
    )


def _matches(row: Mapping[str, object], bundle: LiveOperationalSourceBundle) -> bool:
    expected = bundle.parameters()
    return all(
        bool(row[key]) == value if key == "is_verified" else row[key] == value
        for key, value in expected.items()
    )


def ensure_rl001_live_source(
    connection: Connection,
    bundle: LiveOperationalSourceBundle,
    *,
    apply: bool,
) -> Literal["planned", "inserted", "unchanged"]:
    existing = (
        connection.execute(
            text(
                "SELECT source_snapshot_id, template_id, effective_at, is_verified, "
                "snapshot_payload_json, evidence_payload_json "
                "FROM app.live_operational_sources "
                "WHERE source_snapshot_id = :source_snapshot_id"
            ),
            {"source_snapshot_id": bundle.source_snapshot_id},
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if not _matches(existing, bundle):
            raise RuntimeError(
                "existing RL-001 source differs from the canonical bundle"
            )
        return "unchanged"
    if not apply:
        return "planned"
    connection.execute(
        text(
            "INSERT INTO app.live_operational_sources "
            "(source_snapshot_id, template_id, effective_at, is_verified, "
            "snapshot_payload_json, evidence_payload_json) VALUES "
            "(:source_snapshot_id, :template_id, :effective_at, :is_verified, "
            ":snapshot_payload_json, :evidence_payload_json)"
        ),
        bundle.parameters(),
    )
    return "inserted"
```

- [ ] **Step 4: Run the bundle tests**

Run:

```bash
uv run pytest tests/integrations/test_fabric_demo_source.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Run type, lint, and focused integration checks**

Run:

```bash
uv run ruff check integrations/fabric/demo_source.py tests/integrations/test_fabric_demo_source.py
uv run pyright integrations/fabric/demo_source.py
uv run pytest tests/integrations/test_fabric_demo_source.py tests/integration/test_live_hardening.py -q
```

Expected: all commands pass.

- [ ] **Step 6: Commit the canonical bundle unit**

```bash
git add integrations/fabric/demo_source.py tests/integrations/test_fabric_demo_source.py
git commit -m "feat(fabric): define canonical RL-001 source bundle"
```

### Task 3: Add the guarded loader CLI and verify the live row

**Files:**
- Create: `scripts/load_fabric_rl001.py`
- Create: `tests/integrations/test_load_fabric_rl001.py`
- Modify: `docs/deployment/personal-tenant.md`
- Modify after verified execution: `docs/local/supply-response-personal-environment.md` (gitignored)

**Interfaces:**
- Consumes: `Settings`, `build_credential`, `build_fabric_engine`, `build_rl001_live_source`, `ensure_rl001_live_source`, and `FabricLiveOperationalDataPort`.
- Produces: `run(*, apply: bool, settings: Settings, engine: Engine | None = None) -> Literal["planned", "inserted", "unchanged"]` plus the command `uv run python scripts/load_fabric_rl001.py [--apply]`.

- [ ] **Step 1: Write failing CLI behavior tests**

Create `tests/integrations/test_load_fabric_rl001.py`:

```python
from contextlib import nullcontext
from typing import cast

import pytest
from sqlalchemy import Engine

from apps.api.app.settings import Settings
from data.domain import RuntimeMode
from scripts import load_fabric_rl001


class FakeEngine:
    def __init__(self):
        self.connection = object()
        self.begin_calls = 0
        self.connect_calls = 0

    def begin(self):
        self.begin_calls += 1
        return nullcontext(self.connection)

    def connect(self):
        self.connect_calls += 1
        return nullcontext(self.connection)


def _settings(**changes):
    values = {
        "runtime_mode": RuntimeMode.LIVE,
        "allowed_tenant_id": "11111111-1111-4111-8111-111111111111",
        "fabric_sql_server": "demo.database.fabric.microsoft.com,1433",
        "fabric_sql_database": "SupplyResponseDemo-id",
        "credential_mode": "azure_cli",
        "fabric_citation_base_url": "https://app.powerbi.com/groups/demo/reports/report",
    }
    values.update(changes)
    return Settings(**values)


def test_dry_run_uses_a_read_only_connection(monkeypatch):
    engine = FakeEngine()
    ensure = monkeypatch.setattr(
        load_fabric_rl001,
        "ensure_rl001_live_source",
        lambda connection, bundle, *, apply: "planned",
    )

    result = load_fabric_rl001.run(
        apply=False,
        settings=_settings(),
        engine=cast(Engine, engine),
    )

    assert ensure is None
    assert result == "planned"
    assert engine.connect_calls == 1
    assert engine.begin_calls == 0


def test_apply_uses_one_transaction_and_verifies_readback(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(
        load_fabric_rl001,
        "ensure_rl001_live_source",
        lambda connection, bundle, *, apply: "inserted",
    )
    verified = []
    monkeypatch.setattr(
        load_fabric_rl001,
        "verify_readback",
        lambda active_engine, bundle: verified.append((active_engine, bundle)),
    )

    result = load_fabric_rl001.run(
        apply=True,
        settings=_settings(),
        engine=cast(Engine, engine),
    )

    assert result == "inserted"
    assert engine.begin_calls == 1
    assert engine.connect_calls == 0
    assert len(verified) == 1
    assert verified[0][0] is engine


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"runtime_mode": RuntimeMode.FALLBACK, "database_url": "sqlite://"}, "live runtime"),
        ({"credential_mode": "managed_identity"}, "Azure CLI credential"),
        ({"fabric_citation_base_url": None}, "citation base"),
    ],
)
def test_rejects_an_unsafe_local_loader_environment(changes, message):
    with pytest.raises(SystemExit, match=message):
        load_fabric_rl001.run(
            apply=False,
            settings=_settings(**changes),
            engine=cast(Engine, FakeEngine()),
        )
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
uv run pytest tests/integrations/test_load_fabric_rl001.py -q
```

Expected: collection ERROR because `scripts.load_fabric_rl001` does not exist.

- [ ] **Step 3: Implement the guarded loader and production-adapter readback**

Create `scripts/load_fabric_rl001.py`:

```python
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Engine, text

from apps.api.app.settings import Settings
from data.domain import CasePurpose, RuntimeMode
from data.domain.evidence import AuthorityScope, EvidenceSourceSystem
from integrations.fabric.demo_source import (
    LiveOperationalSourceBundle,
    build_rl001_live_source,
    ensure_rl001_live_source,
)
from integrations.fabric.operational import FabricLiveOperationalDataPort
from services.persistence.fabric_sql import build_credential, build_fabric_engine


async def _retrieve(engine: Engine):
    return await FabricLiveOperationalDataPort(engine).retrieve(
        case_id="RL-CASE-LOADER-VERIFY",
        purpose=CasePurpose.SHOWCASE,
        analysis_id="RL-ANALYSIS-LOADER-VERIFY",
        retrieved_at=datetime.now(UTC),
    )


def verify_readback(engine: Engine, bundle: LiveOperationalSourceBundle) -> None:
    retrieved = asyncio.run(_retrieve(engine))
    if retrieved.source_snapshot_id != bundle.source_snapshot_id:
        raise RuntimeError("Fabric readback returned the wrong source snapshot")
    if retrieved.snapshot.model_copy(update={"case_id": "RL-CASE-TEMPLATE"}) != bundle.snapshot():
        raise RuntimeError("Fabric readback returned a different operational snapshot")
    evidence = retrieved.evidence
    expected_ids = {
        "RL-ALPHA-OPTIONAL-3000",
        "RL-TRANSFER-DAL-CHI-1500",
        "RL-QUALITY-001",
    }
    actual_scopes = {scope for item in evidence for scope in item.authority_scope}
    if (
        {item.evidence_id for item in evidence} != expected_ids
        or actual_scopes
        != {
            AuthorityScope.OPERATIONAL_QUANTITY,
            AuthorityScope.OPERATIONAL_DATE,
            AuthorityScope.QUALIFICATION_STATE,
        }
        or any(item.source_system is not EvidenceSourceSystem.FABRIC for item in evidence)
        or any(item.runtime_mode is not RuntimeMode.LIVE for item in evidence)
        or any(item.synthetic for item in evidence)
    ):
        raise RuntimeError("Fabric readback evidence does not match RL-001")
    with engine.connect() as connection:
        count = connection.execute(
            text(
                "SELECT COUNT(*) FROM app.live_operational_sources "
                "WHERE source_snapshot_id = :source_snapshot_id AND is_verified = 1"
            ),
            {"source_snapshot_id": bundle.source_snapshot_id},
        ).scalar_one()
    if count != 1:
        raise RuntimeError("Fabric does not contain exactly one verified RL-001 source")


def run(
    *,
    apply: bool,
    settings: Settings,
    engine: Engine | None = None,
) -> Literal["planned", "inserted", "unchanged"]:
    if settings.runtime_mode is not RuntimeMode.LIVE:
        raise SystemExit("loader requires live runtime")
    if settings.credential_mode != "azure_cli":
        raise SystemExit("loader requires an Azure CLI credential")
    citation_url = settings.fabric_citation_base_url
    if not citation_url:
        raise SystemExit("loader requires the configured Fabric citation base")
    active_engine = engine or build_fabric_engine(
        settings, build_credential(settings)
    )
    bundle = build_rl001_live_source(citation_url)
    context = active_engine.begin() if apply else active_engine.connect()
    with context as connection:
        outcome = ensure_rl001_live_source(connection, bundle, apply=apply)
    if apply:
        verify_readback(active_engine, bundle)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="insert the verified canonical RL-001 bundle when it is absent",
    )
    args = parser.parse_args()
    outcome = run(apply=args.apply, settings=Settings())
    print(f"RL-001 Fabric source: {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests, lint, typing, and the complete local suite**

Run:

```bash
uv run pytest tests/integrations/test_load_fabric_rl001.py -q
uv run ruff check apps integrations scripts tests
uv run pyright
uv run pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected: all commands pass; the web suite includes 51 tests and the production Vite build succeeds.

- [ ] **Step 5: Document the exact loader procedure**

Add this section to `docs/deployment/personal-tenant.md` immediately after the Fabric schema/grant verification:

````markdown
### Load the canonical RL-001 operational source

The live application fails closed until Fabric contains the verified fictional
RL-001 source bundle. Load it only after schema version 12 and the contained-user
permissions have been verified. The command defaults to a read-only plan and
uses the selected Azure CLI tenant; it never prints credentials or payload JSON.

```bash
set -a
source .azure/supply-response-personal/.env
set +a
export SUPPLY_RESPONSE_RUNTIME_MODE=live
export SUPPLY_RESPONSE_CREDENTIAL_MODE=azure_cli
export SUPPLY_RESPONSE_ALLOWED_TENANT_ID="$AZURE_TENANT_ID"
uv run python scripts/load_fabric_rl001.py
```

After separate approval to insert the verified fictional bundle:

```bash
uv run python scripts/load_fabric_rl001.py --apply
```

The first apply reports `inserted`; an exact repeat reports `unchanged`. A
different payload under `RL-001-OPERATIONAL-V1` fails without updating or
deleting the existing authoritative row.
````

- [ ] **Step 6: Commit the guarded loader**

```bash
git add scripts/load_fabric_rl001.py tests/integrations/test_load_fabric_rl001.py docs/deployment/personal-tenant.md
git commit -m "feat(fabric): add guarded RL-001 loader"
```

- [ ] **Step 7: Run the live dry-run and approved insert**

Load the existing ignored azd environment without printing values:

```bash
set -a
source .azure/supply-response-personal/.env
set +a
export SUPPLY_RESPONSE_RUNTIME_MODE=live
export SUPPLY_RESPONSE_CREDENTIAL_MODE=azure_cli
export SUPPLY_RESPONSE_ALLOWED_TENANT_ID="$AZURE_TENANT_ID"
uv run python scripts/load_fabric_rl001.py
uv run python scripts/load_fabric_rl001.py --apply
uv run python scripts/load_fabric_rl001.py --apply
```

Expected: `planned`, then `inserted`, then `unchanged`; both applies complete production-adapter readback and confirm exactly one verified `RL-001-OPERATIONAL-V1` row.

- [ ] **Step 8: Re-run live readiness and the Alex browser journey**

With the existing exact deployment environment exported, run:

```bash
./scripts/deploy_personal_tenant.sh --smoke
```

Expected: `Live Fabric and Foundry readiness gate passed; no delegated user operation was invoked.`

Open the deployed app, sign in as `agent@willmacdonald.com`, create a showcase Case, analyze it, approve the recommended combined response, verify five decision-linked Execution Actions, start simulated execution, verify ten Simulated Observations, and open the Power BI report.

Expected: the complete live journey uses the same Case, Analysis, and Decision identifiers across the web console and Fabric-backed Power BI views; no `LIVE_SOURCE_UNAVAILABLE` response occurs.

- [ ] **Step 9: Record only observed live evidence**

Update the gitignored `docs/local/supply-response-personal-environment.md` with the loader timestamp, source snapshot ID, insert/no-op result, active revision, and actual browser results. Do not record credentials, tokens, or complete payload JSON. Update tracked `README.md` and `docs/ROADMAP.md` only for gates actually observed, then run:

```bash
git diff --check
git add README.md docs/ROADMAP.md
git commit -m "docs: record Fabric RL-001 live verification"
```

Expected: tracked docs distinguish configured, loaded, smoke-tested, and end-to-end-verified status without claiming any unobserved gate.
