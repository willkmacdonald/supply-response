from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from agents.foundry import validate_project_endpoint
from agents.manifests import AgentManifest, load_manifests

ROOT = Path(__file__).resolve().parents[1]


def _versions_from_environment(
    manifests: tuple[AgentManifest, ...],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in manifests:
        prefix = f"SUPPLY_RESPONSE_FOUNDRY_{item.role.upper()}"
        configured_name = os.getenv(f"{prefix}_NAME", "")
        version = os.getenv(f"{prefix}_VERSION", "")
        if configured_name != item.agent_name or not version or version == "latest":
            raise SystemExit(
                "verify requires exact committed names and pinned versions"
            )
        result[item.agent_name] = version
    return result


def verify(
    root: Path,
    *,
    project: Any | None,
    versions: dict[str, str] | None,
) -> tuple[str, ...]:
    manifests = load_manifests(root)
    if project is None and versions is None:
        return ()
    if project is None or versions is None:
        raise RuntimeError("partial Foundry verification configuration is forbidden")
    if set(versions) != {item.agent_name for item in manifests}:
        raise RuntimeError("Foundry version bindings are incomplete or contain drift")
    checked: list[str] = []
    for manifest in manifests:
        version = versions[manifest.agent_name]
        if not version.isdigit() or version == "0":
            raise RuntimeError(
                "Foundry version bindings must be exact numeric versions"
            )
        remote = project.agents.get_version(
            agent_name=manifest.agent_name,
            agent_version=version,
        )
        definition = remote.definition
        matches = (
            remote.name == manifest.agent_name
            and str(remote.version) == version
            and remote.description == manifest.description
            and definition.model == manifest.model
            and definition.instructions == manifest.instructions
            and list(definition.tools or []) == []
        )
        if not matches:
            raise RuntimeError(
                f"Foundry agent drift detected for {manifest.agent_name}"
            )
        checked.append(f"{manifest.agent_name}={version}")
    return tuple(sorted(checked))


def _live_project():
    endpoint = os.getenv("SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT", "")
    tenant_id = os.getenv("SUPPLY_RESPONSE_ENTRA_TENANT_ID", "")
    if not endpoint or not tenant_id:
        raise SystemExit("live verify requires explicit Foundry endpoint and tenant ID")
    from azure.ai.projects import AIProjectClient
    from azure.identity import AzureCliCredential

    return AIProjectClient(
        endpoint=validate_project_endpoint(endpoint),
        credential=AzureCliCredential(tenant_id=tenant_id),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="perform the separately approved live exact-version verification",
    )
    args = parser.parse_args()
    manifests = load_manifests(ROOT)
    project = _live_project() if args.live else None
    versions = _versions_from_environment(manifests) if args.live else None
    checked = verify(ROOT, project=project, versions=versions)
    if project is None:
        print("Validated three local manifests; no credentials or network used.")
    else:
        for item in checked:
            print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
