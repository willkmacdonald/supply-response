from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents.foundry import validate_project_endpoint
from agents.manifests import TRUSTED_MODEL_DEPLOYMENT, AgentManifest, load_manifests

ROOT = Path(__file__).resolve().parents[1]


def _contract_fingerprint(manifest: AgentManifest) -> str:
    contract = {
        "agent_name": manifest.agent_name,
        "description": manifest.description,
        "instructions_sha256": manifest.instructions_sha256,
        "model": manifest.model,
        "role": manifest.role,
        "tools": [],
    }
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _preflight_model_deployment(project: Any) -> None:
    from azure.core.exceptions import ResourceNotFoundError

    try:
        deployment = project.deployments.get(TRUSTED_MODEL_DEPLOYMENT)
    except ResourceNotFoundError as exc:
        raise RuntimeError(
            f"required model deployment {TRUSTED_MODEL_DEPLOYMENT!r} is missing"
        ) from exc

    if (
        deployment.name != TRUSTED_MODEL_DEPLOYMENT
        or deployment.model_name != TRUSTED_MODEL_DEPLOYMENT
    ):
        raise RuntimeError(
            f"model deployment {TRUSTED_MODEL_DEPLOYMENT!r} must bind to "
            f"{TRUSTED_MODEL_DEPLOYMENT!r}"
        )
    if deployment.provisioning_state != "Succeeded":
        raise RuntimeError(
            f"model deployment {TRUSTED_MODEL_DEPLOYMENT!r} must have "
            "provisioning state 'Succeeded'"
        )


def _matches_manifest(
    remote: Any,
    manifest: AgentManifest,
    fingerprint: str,
) -> bool:
    metadata = remote.metadata or {}
    return (
        remote.name == manifest.agent_name
        and remote.description == manifest.description
        and remote.definition.model == manifest.model
        and remote.definition.instructions == manifest.instructions
        and remote.definition.tools == []
        and metadata.get("supply_response_role") == manifest.role
        and metadata.get("supply_response_contract_sha256") == fingerprint
    )


def publish(
    root: Path,
    *,
    project: Any | None,
    emit: Callable[[str], None] = print,
) -> tuple[str, ...]:
    manifests = load_manifests(root)
    if project is None:
        return ()
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.core.exceptions import ResourceNotFoundError

    _preflight_model_deployment(project)
    emitted: list[str] = []
    for manifest in manifests:
        fingerprint = _contract_fingerprint(manifest)
        metadata = {
            "supply_response_contract_sha256": fingerprint,
            "supply_response_role": manifest.role,
        }
        try:
            versions = list(project.agents.list_versions(manifest.agent_name))
        except ResourceNotFoundError:
            versions = []
        matching = [
            version
            for version in versions
            if (version.metadata or {}).get("supply_response_contract_sha256")
            == fingerprint
        ]
        if len(matching) > 1:
            version_ids = ", ".join(str(version.version) for version in matching)
            raise RuntimeError(
                f"ambiguous matching versions for {manifest.agent_name}: {version_ids}"
            )
        if matching:
            reconciled = matching[0]
            if not _matches_manifest(reconciled, manifest, fingerprint):
                raise RuntimeError(
                    f"remote contract drift for {manifest.agent_name} "
                    f"version {reconciled.version}"
                )
        else:
            reconciled = project.agents.create_version(
                agent_name=manifest.agent_name,
                description=manifest.description,
                definition=PromptAgentDefinition(
                    model=manifest.model,
                    instructions=manifest.instructions,
                    tools=[],
                ),
                metadata=metadata,
            )
        line = f"{reconciled.name}={reconciled.version}"
        emitted.append(line)
        emit(line)
    return tuple(emitted)


def _live_project():
    endpoint = os.getenv("SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT", "")
    tenant_id = os.getenv("SUPPLY_RESPONSE_ENTRA_TENANT_ID", "")
    if not endpoint or not tenant_id:
        raise SystemExit("publish requires explicit Foundry endpoint and tenant ID")
    from azure.ai.projects import AIProjectClient
    from azure.identity import AzureCliCredential

    return AIProjectClient(
        endpoint=validate_project_endpoint(endpoint),
        credential=AzureCliCredential(tenant_id=tenant_id),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish",
        action="store_true",
        help="perform the separately approved live create-version operation",
    )
    args = parser.parse_args()
    project = _live_project() if args.publish else None
    publish(ROOT, project=project)
    if project is None:
        print("Validated three local manifests; no credentials or network used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
