from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents.foundry import validate_project_endpoint
from agents.manifests import load_manifests

ROOT = Path(__file__).resolve().parents[1]


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

    emitted: list[str] = []
    for manifest in manifests:
        created = project.agents.create_version(
            agent_name=manifest.agent_name,
            description=manifest.description,
            definition=PromptAgentDefinition(
                model=manifest.model,
                instructions=manifest.instructions,
                tools=[],
            ),
        )
        line = f"{created.name}={created.version}"
        emitted.append(line)
    for line in sorted(emitted):
        emit(line)
    return tuple(sorted(emitted))


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
