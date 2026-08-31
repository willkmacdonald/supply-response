# Preserve Decisions and create downstream work through a transactional outbox

An approved or rejected Decision is an immutable ledger record and the reference point for all later activity. Approval atomically writes the Decision and an outbox event; idempotent workers create Execution Actions, whose current projections are backed by append-only status and attempt history. This accepts eventual action creation and explicit retry states in exchange for preventing downstream failure, replay, or reanalysis from rewriting the human Decision.
