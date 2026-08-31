from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from agents.foundry import FoundryAgentBinding, build_foundry_agent
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
