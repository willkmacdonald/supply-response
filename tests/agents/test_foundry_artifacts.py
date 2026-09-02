from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from agent_framework import AgentResponse, Content, Message
from azure.core.exceptions import ResourceNotFoundError
from pydantic import ValidationError

from agents.foundry import (
    FoundryAgentBinding,
    FoundryJsonAgent,
    build_foundry_agent,
    validate_project_endpoint,
)
from agents.manifests import (
    TRUSTED_MODEL_DEPLOYMENT,
    AgentManifest,
    ManifestError,
    load_manifests,
)
from scripts.publish_foundry_agents import publish
from scripts.verify_foundry_agents import verify

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def valid_manifest() -> dict[str, object]:
    return {
        "role": "signal",
        "agent_name": "supply-response-signal",
        "model": TRUSTED_MODEL_DEPLOYMENT,
        "instructions_path": ROOT / "agents/signal/instructions.md",
        "instructions": "x" * 100,
        "instructions_sha256": "0" * 64,
        "description": "A valid prompt agent manifest.",
        "tools": (),
    }


class FakeAgents:
    def __init__(
        self,
        events: list[str],
        *,
        fail_after_creations: int | None = None,
    ) -> None:
        self.events = events
        self.fail_after_creations = fail_after_creations
        self.created: list[dict[str, object]] = []
        self.remote: dict[tuple[str, str], object] = {}
        self.versions: dict[str, list[object]] = {}

    def create_version(self, **kwargs):  # allowed: injected SDK test double
        if (
            self.fail_after_creations is not None
            and len(self.created) >= self.fail_after_creations
        ):
            raise RuntimeError("simulated create failure")
        self.created.append(kwargs)
        agent_name = cast(str, kwargs["agent_name"])
        version = str(len(self.versions.get(agent_name, [])) + 1)
        created = SimpleNamespace(
            name=agent_name,
            version=version,
            description=kwargs["description"],
            definition=kwargs["definition"],
            metadata=kwargs["metadata"],
        )
        self.versions.setdefault(agent_name, []).append(created)
        self.events.append(f"create:{agent_name}")
        return created

    def list_versions(self, agent_name: str):
        self.events.append(f"list:{agent_name}")
        return list(self.versions.get(agent_name, []))

    def get_version(self, *, agent_name: str, agent_version: str):
        return self.remote[(agent_name, agent_version)]


class FakeDeployments:
    def __init__(
        self,
        events: list[str],
        *,
        present: bool = True,
        model_name: str = TRUSTED_MODEL_DEPLOYMENT,
        provisioning_state: str = "Succeeded",
    ) -> None:
        self.events = events
        self.present = present
        self.deployment = SimpleNamespace(
            name=TRUSTED_MODEL_DEPLOYMENT,
            model_name=model_name,
            provisioning_state=provisioning_state,
        )

    def get(self, name: str):
        self.events.append(f"deployment:{name}")
        if not self.present:
            raise ResourceNotFoundError("deployment not found")
        return self.deployment


class FakeProject:
    def __init__(
        self,
        *,
        deployment_present: bool = True,
        deployment_model: str = TRUSTED_MODEL_DEPLOYMENT,
        deployment_state: str = "Succeeded",
        fail_after_creations: int | None = None,
    ) -> None:
        self.events: list[str] = []
        self.agents = FakeAgents(
            self.events,
            fail_after_creations=fail_after_creations,
        )
        self.deployments = FakeDeployments(
            self.events,
            present=deployment_present,
            model_name=deployment_model,
            provisioning_state=deployment_state,
        )


def test_committed_manifests_are_frozen_safe_and_tool_free() -> None:
    manifests = load_manifests(ROOT)
    assert [item.role for item in manifests] == ["context", "decision", "signal"]
    assert len({item.agent_name for item in manifests}) == 3
    assert all(item.tools == () for item in manifests)
    assert all(item.instructions_path.is_relative_to(ROOT) for item in manifests)
    assert all(item.instructions_sha256 for item in manifests)


def test_committed_manifests_use_only_the_trusted_model() -> None:
    manifests = load_manifests(ROOT)
    assert TRUSTED_MODEL_DEPLOYMENT == "gpt-5.6-luna"
    assert {manifest.model for manifest in manifests} == {TRUSTED_MODEL_DEPLOYMENT}


def test_manifest_rejects_a_different_model(
    valid_manifest: dict[str, object],
) -> None:
    valid_manifest["model"] = "gpt-4.1-mini"
    with pytest.raises(ValidationError, match="gpt-5.6-luna"):
        AgentManifest.model_validate(valid_manifest)


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


def _expected_fingerprint(manifest: AgentManifest) -> str:
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


def test_publish_preflights_model_before_creating_any_version() -> None:
    project = FakeProject()
    emitted: list[str] = []
    publish(ROOT, project=project, emit=emitted.append)

    assert project.events[0] == f"deployment:{TRUSTED_MODEL_DEPLOYMENT}"
    assert project.events.index(project.events[0]) < next(
        index
        for index, event in enumerate(project.events)
        if event.startswith("create:")
    )


@pytest.mark.parametrize(
    ("project", "message"),
    [
        (FakeProject(deployment_present=False), "missing"),
        (FakeProject(deployment_model="gpt-4.1-mini"), "gpt-5.6-luna"),
        (FakeProject(deployment_state="Failed"), "Succeeded"),
    ],
)
def test_publish_rejects_invalid_model_deployment_before_agent_mutation(
    project: FakeProject,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        publish(ROOT, project=project)

    assert project.agents.created == []


def test_first_publish_creates_three_fingerprinted_versions() -> None:
    project = FakeProject()
    emitted: list[str] = []
    manifests = load_manifests(ROOT)

    result = publish(ROOT, project=project, emit=emitted.append)

    assert len(project.agents.created) == 3
    for manifest, call in zip(manifests, project.agents.created, strict=True):
        assert cast(Any, call["definition"]).tools == []
        assert call["metadata"] == {
            "supply_response_contract_sha256": _expected_fingerprint(manifest),
            "supply_response_role": manifest.role,
        }
    assert result == tuple(emitted)
    assert all(line.count("=") == 1 for line in emitted)
    assert "https://" not in "".join(emitted)


def test_repeat_publish_reuses_every_version_without_creating() -> None:
    project = FakeProject()
    first = publish(ROOT, project=project, emit=lambda _: None)
    project.agents.created.clear()
    emitted: list[str] = []

    second = publish(ROOT, project=project, emit=emitted.append)

    assert project.agents.created == []
    assert second == first
    assert tuple(emitted) == first


def test_failed_publish_retries_without_duplicating_created_version() -> None:
    project = FakeProject(fail_after_creations=1)
    emitted: list[str] = []

    with pytest.raises(RuntimeError, match="simulated create failure"):
        publish(ROOT, project=project, emit=emitted.append)

    assert len(project.agents.created) == 1
    assert emitted == [
        f"{project.agents.created[0]['agent_name']}=1",
    ]

    project.agents.fail_after_creations = None
    project.agents.created.clear()
    retried = publish(ROOT, project=project, emit=emitted.append)

    assert len(project.agents.created) == 2
    assert retried[0] == emitted[0]
    assert len(retried) == 3


def test_publish_rejects_matching_fingerprint_with_remote_field_drift() -> None:
    project = FakeProject()
    publish(ROOT, project=project, emit=lambda _: None)
    existing = project.agents.versions[load_manifests(ROOT)[0].agent_name][0]
    cast(Any, existing).description = "remote drift"
    project.agents.created.clear()

    with pytest.raises(RuntimeError, match="drift"):
        publish(ROOT, project=project, emit=lambda _: None)

    assert project.agents.created == []


def test_publish_rejects_ambiguous_matching_fingerprints() -> None:
    project = FakeProject()
    publish(ROOT, project=project, emit=lambda _: None)
    manifest = load_manifests(ROOT)[0]
    duplicate = SimpleNamespace(**vars(project.agents.versions[manifest.agent_name][0]))
    duplicate.version = "2"
    project.agents.versions[manifest.agent_name].append(duplicate)
    project.agents.created.clear()

    with pytest.raises(RuntimeError, match=f"{manifest.agent_name}.*1.*2"):
        publish(ROOT, project=project, emit=lambda _: None)

    assert project.agents.created == []


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
