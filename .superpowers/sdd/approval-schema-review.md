# Approval schema prerequisite review

## Scope

Reviewed `fabric/sql/001_operational_schema.sql` in `78a6bf5..28f7ec6` and the uncommitted isolated SQL Server upgrade test. No production edits or live operations were performed.

## Assessment

**Approved for the bounded additive prerequisite. No Critical or Important findings.**

The change safely supports applying the current operational script to the known deployed version-12 shape:

- Both Finance tables are created only when absent, after their referenced Case/Analysis tables and before the Case projection foreign key is added.
- Existing `case_projection` rows receive `proposal_generation = 0` and `current_selection_id = NULL`; existing payload JSON is untouched.
- Reapplication is idempotent for tables, columns, constraints and indexes. A partial DDL run can be retried without recreating completed objects.
- Primary, unique, filtered-unique, positive-generation/revision, review-pair, JSON and foreign-key constraints match the accepted SQLAlchemy persistence contract.
- The filtered unique index correctly permits multiple low-cost selections with `NULL` Finance review IDs while enforcing one selection per non-null review.
- The operational script publishes version 11 only when the stored version is lower, so applying it to the deployed version-12 database cannot downgrade or rewrite the version record.
- The isolated test has strong target guardrails (localhost, exact driver, disposable database prefix, empty-database precondition), recreates the deployed legacy omission, preserves representative payloads/version, applies twice, proves defaults, trusted foreign keys, filtered uniqueness and invalid Finance bindings, and verifies row counts afterward.

## Minor observation

The isolated test proves the important composite Finance-review FK and filtered uniqueness, but does not independently attempt invalid values for every newly declared constraint (for example a negative proposal generation or a nonexistent `current_selection_id`). This is not blocking because those declarations directly match the already-tested persistence metadata and the native run verifies all created foreign keys are enabled and trusted.

## Release boundary

Apply only `fabric/sql/001_operational_schema.sql`, then verify pre/post legacy payloads, counts, version 12, new object/column presence, trusted constraints and application health. Do not run reporting scripts or enable the independent workflow until this prerequisite and the remaining browser/session gates are complete.
