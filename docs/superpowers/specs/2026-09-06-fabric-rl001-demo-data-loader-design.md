# Fabric RL-001 Demo Data Loader Design

## Problem

The live application correctly fails closed when Fabric cannot provide a verified operational source. The personal-tenant Fabric SQL database currently has schema version 12 but zero rows in `app.live_operational_sources`, so live Case creation returns `LIVE_SOURCE_UNAVAILABLE`.

The frozen demo contract already defines the required operational data. It also requires a fixed fictional Scenario Effective Time and explicitly states that demo data does not need regeneration within 24 hours of a presentation. The implementation currently has no supported loader and incorrectly compares evidence source/business timestamps with wall-clock analysis time.

## Scope

Add one explicit, reusable loader for the canonical RL-001 operational source bundle and align live evidence time validation with the frozen contract. Then load and verify the existing personal-tenant Fabric SQL database.

This change does not alter RL-001 quantities, dates, calculations, ranking, Work IQ source bindings, Foundry agents, Entra identities, Power BI bindings, schema version, or fallback behavior.

## Considered Approaches

### 1. Repository-owned idempotent loader — selected

Build the canonical payload through typed domain models, require an explicit apply flag, insert it under a stable source ID, and verify it through the production Fabric adapter. This is reproducible, reviewable, portable to another tenant, and safe to rerun.

### 2. One-time manual SQL insert

This is faster for the immediate browser run but duplicates a large JSON contract outside typed code, is difficult to review, and cannot reliably reset or provision another tenant.

### 3. Seed automatically during Case creation

This makes the application manufacture its own authoritative live input when the source is absent. It weakens the fail-closed boundary and makes a live read indistinguishable from fallback fixture creation, so it is rejected.

## Architecture

### Typed source-bundle builder

A focused module will construct one `LiveOperationalSourceBundle` containing:

- stable source snapshot ID `RL-001-OPERATIONAL-V1`;
- template ID `RL-001`;
- effective time `2026-09-01T09:00:00-05:00`;
- `is_verified=True`;
- the existing canonical `OperationalSnapshot.rl001(runtime_mode=LIVE)` payload;
- three typed Fabric `EvidenceItem` records covering operational quantity/date and qualification state.

The evidence records use the existing stable IDs and facts:

| Evidence ID | Fabric source ID | Authority Scope |
| --- | --- | --- |
| `RL-ALPHA-OPTIONAL-3000` | `fabric.supply_receipt/RL-ALPHA-OPTIONAL-3000` | `operational_quantity`, `operational_date` |
| `RL-TRANSFER-DAL-CHI-1500` | `fabric.inventory_transfer/RL-TRANSFER-DAL-CHI-1500` | `operational_quantity`, `operational_date` |
| `RL-QUALITY-001` | `fabric.qualification/RL-QUAL-BETA` | `qualification_state` |

Each citation is derived from the configured canonical `https://app.powerbi.com` report base and contains no credential, token, fragment, or sensitive query parameter. Each item is labeled `runtime_mode=live`, `source_system=fabric`, and `synthetic=false`: those fields describe the integration and authority path. The UI and corpus documentation continue to label the business scenario as fictional/demo data.

### Explicit loader command

`scripts/load_fabric_rl001.py` will use the existing `Settings`, Azure credential, and Fabric engine construction. Its default mode performs validation and prints the intended source ID without writing. `--apply` is required for the transaction that inserts the bundle.

The write is insert-only and idempotent:

- If `RL-001-OPERATIONAL-V1` does not exist, insert it in one transaction.
- If it exists with byte-equivalent canonical JSON and metadata, make no change and report that it is already current.
- If it exists but differs, fail without updating or deleting it. Replacing authoritative source data requires a separately designed and approved operation.

The command never prints access tokens, connection strings, or complete JSON payloads.

### Time semantics

The loader does not stamp demo evidence with the presentation date. Source and business-effective timestamps remain part of the fixed fictional scenario.

At live retrieval:

- `retrieved_at` records the current wall-clock analysis call and proves that Fabric and Work IQ were called for the current Analysis Version.
- `source_timestamp` is retained and must be present, but is not required to be within 24 hours of wall-clock analysis time.
- `effective_at` and `expires_at` express business validity and are evaluated against the Case's Scenario Effective Time, not the presentation date.

This implements the frozen rule that a stable demo corpus can be rehearsed later without regeneration while still proving that each live service was called during the current analysis.

## Data Flow

1. The operator selects the intended azd environment and runs the loader without `--apply`.
2. The loader validates the canonical typed bundle and the exact Fabric target.
3. Under the existing separate cloud-write approval, the operator runs `--apply`.
4. The loader inserts the verified bundle or confirms an exact existing match.
5. The loader reads the row through `FabricLiveOperationalDataPort`, using a new Case ID and Analysis ID, and verifies the source ID, canonical snapshot, three evidence records, Fabric provenance, and authority scopes.
6. Live Case creation reads the same row and persists a new immutable live Case.
7. Live analysis re-reads the row, retrieves Work IQ evidence in the current analysis, invokes the pinned Foundry agents, and persists the immutable Analysis Version.

## Failure and Safety Behavior

- Missing or partial Fabric configuration stops before connection.
- A target other than runtime mode `live` or credential mode `azure_cli` is rejected by the local loader.
- An absent `--apply` flag never writes.
- A mismatched existing stable source ID fails closed without mutation.
- Invalid typed snapshot/evidence data fails before SQL execution.
- SQL or managed-identity failures roll back the transaction and expose only bounded, credential-free diagnostics.
- The application retains its existing `LIVE_SOURCE_UNAVAILABLE` behavior when the verified row is absent or invalid.
- No fallback fixture is created automatically and no fallback Case is substituted.

## Verification

Automated tests will prove:

1. The builder produces the exact frozen RL-001 facts, stable source identifiers, authority scopes, live Fabric provenance, and fictional scenario time.
2. Dry-run performs no SQL mutation.
3. First apply inserts exactly one canonical bundle.
4. A second exact apply is a no-op.
5. An existing mismatched source ID fails without update or deletion.
6. Live evidence boundary validation uses wall clock only for `retrieved_at` and uses Scenario Effective Time for business validity.
7. The full existing unit and integration suites remain green.

The approved live verification will then:

1. apply the loader to the personal-tenant Fabric SQL database;
2. read back `RL-001-OPERATIONAL-V1` through the production adapter;
3. confirm the table contains exactly one verified canonical row;
4. rerun the user-context-free deployment smoke gate;
5. resume the Alex-authenticated Case, analysis, decision, execution, outcomes, and Power BI journey.
