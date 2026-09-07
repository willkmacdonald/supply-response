"""Approval-gated legacy A2A adapter check; not production MCP acceptance."""

from __future__ import annotations

import os
import stat
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

LIVE_SETTINGS = (
    "SUPPLY_RESPONSE_WORKIQ_LIVE",
    "SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
    "SUPPLY_RESPONSE_API_CLIENT_ID",
    "SUPPLY_RESPONSE_API_CLIENT_SECRET",
    "SUPPLY_RESPONSE_ALEX_OBJECT_ID",
    "SUPPLY_RESPONSE_WORKIQ_ALEX_ASSERTION_FILE",
    "SUPPLY_RESPONSE_WORKIQ_ALPHA_SOURCE_ID",
    "SUPPLY_RESPONSE_WORKIQ_BETA_SOURCE_ID",
    "SUPPLY_RESPONSE_WORKIQ_TENANT_SHAREPOINT_HOST",
    "SUPPLY_RESPONSE_WORKIQ_ALEX_STORAGE_STATE_FILE",
)
configured = {name: os.environ.get(name, "").strip() for name in LIVE_SETTINGS}
present = {name for name, value in configured.items() if value}

if not present:
    pytestmark = [
        pytest.mark.workiq_live,
        pytest.mark.skip(reason="Work IQ live settings are not configured"),
    ]
elif present != set(LIVE_SETTINGS):
    missing = sorted(set(LIVE_SETTINGS) - present)
    raise pytest.UsageError(
        "Work IQ live settings must be configured together before any "
        "authentication or network access; missing: " + ", ".join(missing)
    )
elif configured["SUPPLY_RESPONSE_WORKIQ_LIVE"] != "1":
    raise pytest.UsageError("SUPPLY_RESPONSE_WORKIQ_LIVE must be exactly 1")
else:
    pytestmark = pytest.mark.workiq_live


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _fresh_alex_assertion() -> str:
    path = Path(configured["SUPPLY_RESPONSE_WORKIQ_ALEX_ASSERTION_FILE"])
    try:
        info = path.stat()
    except OSError as error:
        raise AssertionError("Alex assertion file is not readable") from error
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise AssertionError("Alex assertion file must be owner-only")
    if time.time() - info.st_mtime > 600:
        raise AssertionError(
            "Alex delegated assertion must be less than ten minutes old"
        )
    if info.st_size <= 0 or info.st_size > 32_768:
        raise AssertionError("Alex delegated assertion file size is invalid")
    assertion = path.read_text().strip()
    if assertion.count(".") != 2:
        raise AssertionError("Alex delegated assertion is malformed")
    return assertion


def _alex_storage_state() -> Path:
    path = Path(configured["SUPPLY_RESPONSE_WORKIQ_ALEX_STORAGE_STATE_FILE"])
    try:
        info = path.stat()
    except OSError as error:
        raise AssertionError(
            "Alex browser storage-state file is not readable"
        ) from error
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise AssertionError("Alex browser storage-state file must be owner-only")
    if info.st_size <= 0 or info.st_size > 1_048_576:
        raise AssertionError("Alex browser storage-state file size is invalid")
    return path


@pytest.mark.anyio
async def test_alex_retrieves_current_cited_demo_corpus() -> None:
    from apps.api.app.auth import AuthService, PersonaBinding
    from data.domain.evidence import EvidenceRequirement
    from integrations.workiq.citations import (
        CitationExpectation,
        PlaywrightCitationVerifier,
    )
    from integrations.workiq.client import WorkIQClient, WorkIQEvidencePort
    from integrations.workiq.obo import build_obo_exchange

    retrieved_at = datetime.now(UTC)
    storage_state_path = _alex_storage_state()
    tenant_id = configured["SUPPLY_RESPONSE_ALLOWED_TENANT_ID"]
    auth = AuthService(
        tenant_id=tenant_id,
        audience=configured["SUPPLY_RESPONSE_API_CLIENT_ID"],
        bindings=(
            PersonaBinding.alex(
                tenant_id,
                configured["SUPPLY_RESPONSE_ALEX_OBJECT_ID"],
            ),
        ),
    )
    actor = auth.authenticate(_fresh_alex_assertion())
    obo = build_obo_exchange(
        client_id=configured["SUPPLY_RESPONSE_API_CLIENT_ID"],
        client_secret=configured["SUPPLY_RESPONSE_API_CLIENT_SECRET"],
        tenant_id=tenant_id,
        auth_service=auth,
    )
    async with httpx.AsyncClient() as http:
        port = WorkIQEvidencePort(
            client=WorkIQClient(http=http),
            obo=obo,
            tenant_sharepoint_host=configured[
                "SUPPLY_RESPONSE_WORKIQ_TENANT_SHAREPOINT_HOST"
            ],
        )
        alpha = await port.retrieve_supplier_signal(
            actor=actor,
            source_id=configured["SUPPLY_RESPONSE_WORKIQ_ALPHA_SOURCE_ID"],
            case_id="RL-CASE-WORKIQ-LIVE",
            analysis_id="RL-ANALYSIS-WORKIQ-LIVE",
            retrieved_at=retrieved_at,
        )
        beta = await port.retrieve_quality_context(
            actor=actor,
            source_id=configured["SUPPLY_RESPONSE_WORKIQ_BETA_SOURCE_ID"],
            case_id="RL-CASE-WORKIQ-LIVE",
            analysis_id="RL-ANALYSIS-WORKIQ-LIVE",
            retrieved_at=retrieved_at,
        )
        items = (*alpha.evidence, *beta.evidence)
        assert items
        assert all(
            item.requirement is EvidenceRequirement.REQUIRED_AUTHORITATIVE
            for item in items
        )
        assert all(item.retrieved_at == retrieved_at for item in items)
        assert all(item.citation_url for item in items)
        citation_expectations = tuple(
            CitationExpectation(
                url=item.citation_url,
                expected_excerpt=item.excerpt,
                source_identity=item.source_id,
            )
            for item in items
            if item.citation_url is not None and item.excerpt is not None
        )
        assert len(citation_expectations) == len(items)
        verifier = PlaywrightCitationVerifier(
            storage_state_path=storage_state_path,
            tenant_sharepoint_host=configured[
                "SUPPLY_RESPONSE_WORKIQ_TENANT_SHAREPOINT_HOST"
            ],
        )
        await verifier.verify(citation_expectations)
