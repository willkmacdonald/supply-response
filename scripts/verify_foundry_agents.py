from __future__ import annotations

import argparse
import hashlib
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
        configured_name = os.getenv(f"{prefix}_AGENT_NAME", "")
        version = os.getenv(f"{prefix}_AGENT_VERSION", "")
        if (
            configured_name != item.agent_name
            or not version.isdigit()
            or version.startswith("0")
        ):
            raise SystemExit(
                "verify requires exact committed names and pinned versions"
            )
        result[item.agent_name] = version
    return result


def deployment_receipt(
    project_endpoint: str,
    versions: tuple[tuple[str, str], ...],
) -> str:
    """Bind the endpoint and exact signal/context/decision versions."""
    if (
        not isinstance(versions, tuple)
        or len(versions) != 3
        or any(not isinstance(item, tuple) or len(item) != 2 for item in versions)
    ):
        raise TypeError("versions must be an ordered signal/context/decision tuple")
    parts = (project_endpoint,) + tuple(
        part for name_version in versions for part in name_version
    )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


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
    versions = _versions_from_environment(manifests) if args.live else None
    project = _live_project() if args.live else None
    checked = verify(ROOT, project=project, versions=versions)
    if project is None:
        print("Validated three local manifests; no credentials or network used.")
    else:
        assert versions is not None
        for item in checked:
            print(item)
        manifests_by_role = {item.role: item for item in manifests}
        ordered_versions = tuple(
            (
                manifests_by_role[role].agent_name,
                versions[manifests_by_role[role].agent_name],
            )
            for role in ("signal", "context", "decision")
        )
        print(
            "SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT="
            + deployment_receipt(
                os.environ["SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT"],
                ordered_versions,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
