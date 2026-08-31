from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from agent_framework import AgentResponse, Content, Message

from agents.foundry import (
    FoundryAgentBinding,
    FoundryJsonAgent,
    build_foundry_agent,
    validate_project_endpoint,
)
from agents.manifests import ManifestError, load_manifests
from scripts.publish_foundry_agents import publish
from scripts.verify_foundry_agents import verify

ROOT = Path(__file__).resolve().parents[2]


class FakeAgents:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.remote: dict[tuple[str, str], object] = {}

    def create_version(self, **kwargs):  # allowed: injected SDK test double
        self.created.append(kwargs)
        return type("Created", (), {"name": kwargs["agent_name"], "version": "7"})()

    def get_version(self, *, agent_name: str, agent_version: str):
        return self.remote[(agent_name, agent_version)]


class FakeProject:
    def __init__(self) -> None:
        self.agents = FakeAgents()


def test_committed_manifests_are_frozen_safe_and_tool_free() -> None:
    manifests = load_manifests(ROOT)
    assert [item.role for item in manifests] == ["context", "decision", "signal"]
    assert len({item.agent_name for item in manifests}) == 3
    assert all(item.tools == () for item in manifests)
    assert all(item.instructions_path.is_relative_to(ROOT) for item in manifests)
    assert all(item.instructions_sha256 for item in manifests)


def test_manifest_loader_rejects_path_escape_duplicate_names_and_extra_fields(
    tmp_path: Path,
) -> None:
    (tmp_path / "agents/manifests").mkdir(parents=True)
    payload = {
        "agent_name": "supply-response-signal",
        "model": "gpt-4.1-mini",
        "instructions_path": "../secret.txt",
        "description": "safe",
        "tools": [],
        "surprise": True,
    }
    (tmp_path / "agents/manifests/a.json").write_text(json.dumps(payload))
    with pytest.raises(ManifestError):
        load_manifests(tmp_path)


def _copy_agent_artifacts(root: Path) -> None:
    shutil.copytree(ROOT / "agents", root / "agents")


def test_manifest_loader_rejects_manifest_symlink(tmp_path: Path) -> None:
    _copy_agent_artifacts(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text((tmp_path / "agents/manifests/signal.json").read_text())
    (tmp_path / "agents/manifests/signal.json").unlink()
    (tmp_path / "agents/manifests/signal.json").symlink_to(outside)
    with pytest.raises(ManifestError, match="manifest"):
        load_manifests(tmp_path)


def test_manifest_loader_freezes_role_instruction_mapping(tmp_path: Path) -> None:
    _copy_agent_artifacts(tmp_path)
    path = tmp_path / "agents/manifests/signal.json"
    payload = json.loads(path.read_text())
    payload["instructions_path"] = "agents/context/instructions.md"
    path.write_text(json.dumps(payload))
    with pytest.raises(ManifestError, match="instruction"):
        load_manifests(tmp_path)


def test_foundry_agent_requires_trusted_exact_binding() -> None:
    captured: dict[str, object] = {}

    def constructor(**kwargs):
        captured.update(kwargs)
        return object()

    binding = FoundryAgentBinding(
        project_endpoint="https://example.services.ai.azure.com/api/projects/demo",
        agent_name="supply-response-signal",
        agent_version="7",
    )
    build_foundry_agent(binding, credential=object(), constructor=constructor)
    assert captured["agent_version"] == "7"
    assert captured["agent_name"] == "supply-response-signal"
    with pytest.raises(ValueError):
        FoundryAgentBinding(
            project_endpoint="https://example.invalid/project?token=secret",
            agent_name="supply-response-signal",
            agent_version="latest",
        )


def test_foundry_endpoint_accepts_only_canonical_project_origin() -> None:
    endpoint = "https://example.services.ai.azure.com/api/projects/demo-project_1"
    assert validate_project_endpoint(endpoint) == endpoint
    assert (
        FoundryAgentBinding(
            project_endpoint=endpoint,
            agent_name="supply-response-signal",
            agent_version="7",
        ).project_endpoint
        == endpoint
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.services.ai.azure.com/api/projects/demo",
        "https://user:secret@example.services.ai.azure.com/api/projects/demo",
        "https://example.services.ai.azure.com:443/api/projects/demo",
        "https://example.services.ai.azure.com:444/api/projects/demo",
        "https://example.services.ai.azure.com/api/projects/demo?token=secret",
        "https://example.services.ai.azure.com/api/projects/demo#fragment",
        "https://example.services.ai.azure.com/api/projects/demo/extra",
        "https://example.services.ai.azure.com/api/projects/../demo",
        "https://EXAMPLE.services.ai.azure.com/api/projects/demo",
        "https://example.evil.services.ai.azure.com/api/projects/demo",
        "https://services.ai.azure.com/api/projects/demo",
        "https://127.0.0.1/api/projects/demo",
        "https://localhost/api/projects/demo",
        "https://*.services.ai.azure.com/api/projects/demo",
        "https://example.services.ai.azure.com/api/projects/demo%2fescape",
        "https://example.services.ai.azure.com/api/projects/demo value",
    ],
)
def test_foundry_endpoint_rejects_noncanonical_or_credentialed_values(
    endpoint: str,
) -> None:
    with pytest.raises(ValueError, match="trusted"):
        validate_project_endpoint(endpoint)
    with pytest.raises(ValueError, match="trusted"):
        FoundryAgentBinding(
            project_endpoint=endpoint,
            agent_name="supply-response-signal",
            agent_version="7",
        )


@pytest.mark.anyio
async def test_foundry_response_rejects_tool_content_alongside_valid_json() -> None:
    class Agent:
        async def run(self, prompt: str) -> AgentResponse:
            return AgentResponse(
                messages=[
                    Message(
                        "assistant",
                        [
                            Content(
                                type="function_call",
                                call_id="1",
                                name="danger",
                                arguments="{}",
                            ),
                            Content(
                                type="text", text='{"facts":[],"uncertainties":[]}'
                            ),
                        ],
                    )
                ]
            )

    with pytest.raises(RuntimeError, match="plain text"):
        await FoundryJsonAgent(Agent()).invoke({"evidence": []})


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content_type",
    [
        "function_result",
        "mcp_server_tool_call",
        "hosted_tool_call",
        "code_interpreter_tool_call",
        "approval_request",
    ],
)
async def test_foundry_response_rejects_every_non_text_content(
    content_type: str,
) -> None:
    class Agent:
        async def run(self, prompt: str) -> AgentResponse:
            return AgentResponse(
                messages=[Message("assistant", [Content(type=cast(Any, content_type))])]
            )

    with pytest.raises(RuntimeError, match="plain text"):
        await FoundryJsonAgent(Agent()).invoke({"evidence": []})


def test_publish_uses_create_version_and_prints_only_name_version() -> None:
    project = FakeProject()
    emitted: list[str] = []
    publish(ROOT, project=project, emit=emitted.append)
    assert len(project.agents.created) == 3
    assert all(
        cast(Any, call["definition"]).tools == [] for call in project.agents.created
    )
    assert emitted == sorted(emitted)
    assert all(line.count("=") == 1 for line in emitted)
    assert "https://" not in "".join(emitted)


def test_verify_rejects_remote_instruction_or_tool_drift() -> None:
    project = FakeProject()
    manifests = load_manifests(ROOT)
    versions = {item.agent_name: "7" for item in manifests}
    for item in manifests:
        project.agents.remote[(item.agent_name, "7")] = type(
            "Remote",
            (),
            {
                "name": item.agent_name,
                "version": "7",
                "description": item.description,
                "definition": type(
                    "Definition",
                    (),
                    {
                        "model": item.model,
                        "instructions": item.instructions,
                        "tools": [],
                    },
                )(),
            },
        )()
    verify(ROOT, project=project, versions=versions)
    cast(
        Any, project.agents.remote[(manifests[0].agent_name, "7")]
    ).definition.tools = ["web"]
    with pytest.raises(RuntimeError, match="drift"):
        verify(ROOT, project=project, versions=versions)


def test_publish_and_verify_default_to_offline_validation(monkeypatch) -> None:
    monkeypatch.delenv("SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("SUPPLY_RESPONSE_FOUNDRY_PUBLISH", raising=False)
    assert publish(ROOT, project=None, emit=lambda _: None) == ()
    assert verify(ROOT, project=None, versions=None) == ()


def test_live_verify_validates_bindings_before_constructing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.verify_foundry_agents as script

    manifests = load_manifests(ROOT)
    monkeypatch.setattr(sys, "argv", ["verify_foundry_agents.py", "--live"])
    monkeypatch.setenv(
        "SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("SUPPLY_RESPONSE_ENTRA_TENANT_ID", "tenant")
    for item in manifests:
        prefix = f"SUPPLY_RESPONSE_FOUNDRY_{item.role.upper()}"
        monkeypatch.setenv(f"{prefix}_NAME", item.agent_name)
        monkeypatch.delenv(f"{prefix}_VERSION", raising=False)

    constructed = False

    def forbidden_project():
        nonlocal constructed
        constructed = True
        raise AssertionError("credential/client construction occurred")

    monkeypatch.setattr(script, "_live_project", forbidden_project)
    with pytest.raises(SystemExit, match="pinned versions"):
        script.main()
    assert not constructed
