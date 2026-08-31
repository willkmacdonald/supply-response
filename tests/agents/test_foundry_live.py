from __future__ import annotations

import os

import pytest

REQUIRED = (
    "SUPPLY_RESPONSE_ENTRA_TENANT_ID",
    "SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT",
    "SUPPLY_RESPONSE_FOUNDRY_SIGNAL_NAME",
    "SUPPLY_RESPONSE_FOUNDRY_SIGNAL_VERSION",
    "SUPPLY_RESPONSE_FOUNDRY_CONTEXT_NAME",
    "SUPPLY_RESPONSE_FOUNDRY_CONTEXT_VERSION",
    "SUPPLY_RESPONSE_FOUNDRY_DECISION_NAME",
    "SUPPLY_RESPONSE_FOUNDRY_DECISION_VERSION",
    "SUPPLY_RESPONSE_FOUNDRY_LIVE",
)


@pytest.mark.anyio
@pytest.mark.foundry_live
async def test_foundry_live_rl001_requires_complete_exact_bindings() -> None:
    missing = [name for name in REQUIRED if not os.getenv(name)]
    if missing:
        pytest.skip("Foundry live settings are incomplete; no credential was created.")
    assert os.environ["SUPPLY_RESPONSE_FOUNDRY_LIVE"] == "1"
    assert all(os.environ[name] != "latest" for name in REQUIRED if "VERSION" in name)

    from pathlib import Path

    from azure.identity import AzureCliCredential

    from agents.foundry import (
        FoundryAgentBinding,
        build_foundry_agent_set,
    )
    from agents.manifests import load_manifests

    root = Path(__file__).resolve().parents[2]
    manifests = {item.role: item for item in load_manifests(root)}
    endpoint = os.environ["SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT"]
    bindings = {
        role: FoundryAgentBinding(
            project_endpoint=endpoint,
            agent_name=os.environ[f"SUPPLY_RESPONSE_FOUNDRY_{role.upper()}_NAME"],
            agent_version=os.environ[f"SUPPLY_RESPONSE_FOUNDRY_{role.upper()}_VERSION"],
        )
        for role in manifests
    }
    assert all(
        bindings[role].agent_name == manifest.agent_name
        for role, manifest in manifests.items()
    )
    credential = AzureCliCredential(
        tenant_id=os.environ["SUPPLY_RESPONSE_ENTRA_TENANT_ID"]
    )
    agent_set = build_foundry_agent_set(bindings=bindings, credential=credential)
    signal = await agent_set.signal.invoke(
        {
            "evidence": [
                {
                    "evidence_id": "RL-E-FOUNDRY-SMOKE",
                    "authority_scope": ["supplier_statement"],
                    "claim": "Fictional Alpha states that shipment timing is uncertain.",
                    "excerpt": "Fictional Alpha states that shipment timing is uncertain.",
                }
            ]
        }
    )
    assert set(signal) == {"facts", "uncertainties"}
