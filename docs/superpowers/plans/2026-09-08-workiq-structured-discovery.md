# Structured Work IQ Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace answer-link discovery with bounded Work IQ entity queries and reconcile the verified supplier binding.

**Architecture:** A focused structured-discovery module constructs fixed read paths and validates bounded results. The existing evidence port retains authentication, individual fetch, validation, timeout and lineage.

**Tech Stack:** Python, httpx MCP, pytest, existing Azure Container App.

## Global Constraints

- Follow docs/superpowers/specs/2026-09-08-workiq-structured-discovery-design.md.
- No configured-ID discovery input/fallback, direct Graph, pagination, permission changes, or source edits.
- Keep existing transport limits, validators and 120-second per-source deadline.
- Preserve existing dirty changes. No push. Cloud work is controller-owned.

## Task 1: Structured discovery and production wiring

Files: create integrations/workiq/structured_discovery.py and focused tests;
modify integrations/workiq/mcp_evidence.py and evidence/live-wiring tests.
Keep existing ask/locator utility tests for supported legacy parsing; remove only
obsolete production ask expectations, replacing each safety assertion with its
structured counterpart. Do not alter message_evidence.py validation policy.

Interface: async discover_structured(session, *, source_kind, binding) returns
tuple[MessageLocation, ...]. The session exposes async fetch(path) with the
existing validated results/data envelope. Never use binding source IDs to build
paths. Trusted Team/channel IDs may only validate independently returned names
before querying their child resources.

- [ ] Write and run failing tests before code. A request-recording fake session
  serves collections and verifies `await session.fetch(path)` never calls ask.
  Cover empty/duplicate/malformed/oversized/nextLink, hostile IDs, wrong scope,
  invalid source IDs, author/body mismatch, no saved-ID fallback and cancellation.
- [ ] Implement the bounded query path:
  `MAIL_QUERY = '/me/messages?$search=%22RL-Supplier%20Alpha%22&$top=5&$select=id,subject,from,receivedDateTime'`;
  Teams resolve `/me/joinedTeams`, exact displayName, returned-ID channels path,
  exact General, then returned-ID `/messages?$top=10`. Use quote and existing
  strict parse_location to validate identities before requests. Require a unique
  topic/author candidate; do not use expected message ID to disambiguate.
- [ ] Replace production ask call with discover_structured. Keep source-binding
  check before individual fetch and evidence_from_message afterward. Set
  context_id='' for structured requests and retain session.request_ids. Emit only
  constant failure categories, not upstream data.
- [ ] Run `.venv/bin/pytest tests/integration/test_workiq* -q`; update API wiring
  fakes to return documented collections and preserve real auth/OBO seam.
- [ ] Run scoped Ruff/Pyright; report exact RED/GREEN results and changed files.
- [ ] Independent spec/quality review; resolve important findings.

## Task 2: Controller binding, release checks and acceptance

- [ ] Reconcile supplier through the independently discovered exact-corpus email,
  using a temporary memory-only read-only CLI script, then existing validator.
- [ ] Save only the verified ID/receipt to ignored environment via apply_patch;
  preserve old binding in ignored rollback notes. No raw body/token persistence.
- [ ] Update README/roadmap/result notes to distinguish structured discovery from
  semantic ask; do not claim deployed acceptance prematurely.
- [ ] Full pytest, frontend tests/build, package/static checks, git diff --check.
- [ ] Follow azure-validate and azure-deploy for existing app and current scope;
  no new resources or roles. One normal Alex analysis after healthy deployment.
- [ ] Record actual result and any remaining blocker without another blind retry.
