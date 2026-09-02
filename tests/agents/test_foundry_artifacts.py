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
from azure.ai.projects.models import AgentVersionStatus
from azure.core.exceptions import ResourceNotFoundError
from pydantic import ValidationError

import scripts.verify_foundry_agents as verify_script
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
        list_versions_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.fail_after_creations = fail_after_creations
        self.list_versions_error = list_versions_error
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
        if self.list_versions_error is not None:
            return LazyVersionPage(self.list_versions_error)
        return list(self.versions.get(agent_name, []))

    def get_version(self, *, agent_name: str, agent_version: str):
        return self.remote[(agent_name, agent_version)]


class LazyVersionPage:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def __iter__(self):
        raise self.error


class FakeDeployments:
    def __init__(
        self,
        events: list[str],
        *,
        present: bool = True,
        name: str = TRUSTED_MODEL_DEPLOYMENT,
        model_name: str = TRUSTED_MODEL_DEPLOYMENT,
    ) -> None:
        self.events = events
        self.present = present
        self.deployment = SimpleNamespace(
            name=name,
            model_name=model_name,
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
        deployment_name: str = TRUSTED_MODEL_DEPLOYMENT,
        deployment_model: str = TRUSTED_MODEL_DEPLOYMENT,
        fail_after_creations: int | None = None,
        list_versions_error: Exception | None = None,
    ) -> None:
        self.events: list[str] = []
        self.agents = FakeAgents(
            self.events,
            fail_after_creations=fail_after_creations,
            list_versions_error=list_versions_error,
        )
        self.deployments = FakeDeployments(
            self.events,
            present=deployment_present,
            name=deployment_name,
            model_name=deployment_model,
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
async def test_foundry_response_accepts_reasoning_alongside_valid_json() -> None:
    class Agent:
        async def run(self, prompt: str) -> AgentResponse:
            return AgentResponse(
                messages=[
                    Message(
                        "assistant",
                        [
                            Content(type="text_reasoning", text="private reasoning"),
                            Content(
                                type="text", text='{"facts":[],"uncertainties":[]}'
                            ),
                        ],
                    )
                ]
            )

    assert await FoundryJsonAgent(Agent()).invoke({"evidence": []}) == {
        "facts": [],
        "uncertainties": [],
    }


@pytest.mark.anyio
async def test_foundry_response_rejects_reasoning_without_json_text() -> None:
    class Agent:
        async def run(self, prompt: str) -> AgentResponse:
            return AgentResponse(
                messages=[
                    Message(
                        "assistant",
                        [Content(type="text_reasoning", text="private reasoning")],
                    )
                ]
            )

    with pytest.raises(RuntimeError, match="bounded JSON"):
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


def test_publish_accepts_live_sdk_deployment_shape() -> None:
    project = FakeProject()

    publish(ROOT, project=project, emit=lambda _: None)

    assert len(project.agents.created) == 3


@pytest.mark.parametrize(
    ("project", "message"),
    [
        (FakeProject(deployment_present=False), "missing"),
        (FakeProject(deployment_name="gpt-4.1-mini"), "gpt-5.6-luna"),
        (FakeProject(deployment_model="gpt-4.1-mini"), "gpt-5.6-luna"),
    ],
)
def test_publish_rejects_invalid_model_deployment_before_agent_mutation(
    project: FakeProject,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        publish(ROOT, project=project)

    assert project.events == [f"deployment:{TRUSTED_MODEL_DEPLOYMENT}"]


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


def test_repeat_publish_reuses_tool_free_version_with_none_tools() -> None:
    project = FakeProject()
    first = publish(ROOT, project=project, emit=lambda _: None)
    for versions in project.agents.versions.values():
        cast(Any, versions[0]).definition.tools = None
    project.agents.created.clear()

    second = publish(ROOT, project=project, emit=lambda _: None)

    assert project.agents.created == []
    assert second == first


def test_publish_treats_lazy_page_not_found_as_no_existing_versions() -> None:
    project = FakeProject(
        list_versions_error=ResourceNotFoundError("agent not found during iteration")
    )

    publish(ROOT, project=project, emit=lambda _: None)

    assert len(project.agents.created) == 3


def test_publish_propagates_other_lazy_page_iteration_errors() -> None:
    project = FakeProject(list_versions_error=RuntimeError("version page unavailable"))

    with pytest.raises(RuntimeError, match="version page unavailable"):
        publish(ROOT, project=project, emit=lambda _: None)

    assert project.agents.created == []


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


def test_publish_rejects_draft_matching_version() -> None:
    project = FakeProject()
    publish(ROOT, project=project, emit=lambda _: None)
    first_versions = next(iter(project.agents.versions.values()))
    cast(Any, first_versions[0]).draft = True
    project.agents.created.clear()

    with pytest.raises(RuntimeError, match="drift"):
        publish(ROOT, project=project, emit=lambda _: None)

    assert project.agents.created == []


@pytest.mark.parametrize(
    "status",
    (
        AgentVersionStatus.CREATING,
        AgentVersionStatus.FAILED,
        AgentVersionStatus.DELETING,
        AgentVersionStatus.DELETED,
    ),
)
def test_publish_rejects_matching_version_that_is_not_active(
    status: AgentVersionStatus,
) -> None:
    project = FakeProject()
    publish(ROOT, project=project, emit=lambda _: None)
    first_versions = next(iter(project.agents.versions.values()))
    cast(Any, first_versions[0]).status = status
    project.agents.created.clear()

    with pytest.raises(RuntimeError, match="drift"):
        publish(ROOT, project=project, emit=lambda _: None)

    assert project.agents.created == []


@pytest.mark.parametrize("status", (AgentVersionStatus.ACTIVE, "active", None))
def test_publish_reuses_active_or_unspecified_immutable_version(
    status: AgentVersionStatus | str | None,
) -> None:
    project = FakeProject()
    expected = publish(ROOT, project=project, emit=lambda _: None)
    for versions in project.agents.versions.values():
        cast(Any, versions[0]).draft = None
        cast(Any, versions[0]).status = status
    project.agents.created.clear()

    assert publish(ROOT, project=project, emit=lambda _: None) == expected
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


def _set_foundry_binding_environment(
    monkeypatch: pytest.MonkeyPatch,
    versions_by_role: dict[str, str],
    *,
    canonical: bool,
) -> None:
    for item in load_manifests(ROOT):
        prefix = f"SUPPLY_RESPONSE_FOUNDRY_{item.role.upper()}"
        infix = "_AGENT" if canonical else ""
        monkeypatch.setenv(f"{prefix}{infix}_NAME", item.agent_name)
        monkeypatch.setenv(f"{prefix}{infix}_VERSION", versions_by_role[item.role])


def _set_exact_remote_versions(
    project: FakeProject,
    versions_by_role: dict[str, str],
) -> None:
    for item in load_manifests(ROOT):
        version = versions_by_role[item.role]
        project.agents.remote[(item.agent_name, version)] = SimpleNamespace(
            name=item.agent_name,
            version=version,
            description=item.description,
            definition=SimpleNamespace(
                model=item.model,
                instructions=item.instructions,
                tools=[],
            ),
        )


def test_verify_rejects_draft_immutable_version() -> None:
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    project = FakeProject()
    _set_exact_remote_versions(project, versions_by_role)
    manifest = load_manifests(ROOT)[0]
    remote = project.agents.remote[
        (manifest.agent_name, versions_by_role[manifest.role])
    ]
    cast(Any, remote).draft = True

    with pytest.raises(RuntimeError, match="drift"):
        verify(
            ROOT,
            project=project,
            versions={
                item.agent_name: versions_by_role[item.role]
                for item in load_manifests(ROOT)
            },
        )


@pytest.mark.parametrize("status", ("creating", "failed", "deleting", "deleted"))
def test_verify_rejects_immutable_version_that_is_not_active(status: str) -> None:
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    project = FakeProject()
    _set_exact_remote_versions(project, versions_by_role)
    manifest = load_manifests(ROOT)[0]
    remote = project.agents.remote[
        (manifest.agent_name, versions_by_role[manifest.role])
    ]
    cast(Any, remote).status = status

    with pytest.raises(RuntimeError, match="drift"):
        verify(
            ROOT,
            project=project,
            versions={
                item.agent_name: versions_by_role[item.role]
                for item in load_manifests(ROOT)
            },
        )


@pytest.mark.parametrize("status", (AgentVersionStatus.ACTIVE, "active", None))
def test_verify_accepts_active_or_unspecified_immutable_version(
    status: AgentVersionStatus | str | None,
) -> None:
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    project = FakeProject()
    _set_exact_remote_versions(project, versions_by_role)
    for remote in project.agents.remote.values():
        cast(Any, remote).draft = None
        cast(Any, remote).status = status

    verify(
        ROOT,
        project=project,
        versions={
            item.agent_name: versions_by_role[item.role]
            for item in load_manifests(ROOT)
        },
    )


def test_verify_reads_canonical_agent_environment_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    _set_foundry_binding_environment(monkeypatch, versions_by_role, canonical=True)

    assert verify_script._versions_from_environment(load_manifests(ROOT)) == {
        item.agent_name: versions_by_role[item.role] for item in load_manifests(ROOT)
    }


def test_verify_rejects_legacy_environment_bindings_without_agent_infix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    for item in load_manifests(ROOT):
        prefix = f"SUPPLY_RESPONSE_FOUNDRY_{item.role.upper()}"
        monkeypatch.delenv(f"{prefix}_AGENT_NAME", raising=False)
        monkeypatch.delenv(f"{prefix}_AGENT_VERSION", raising=False)
    _set_foundry_binding_environment(monkeypatch, versions_by_role, canonical=False)

    with pytest.raises(SystemExit, match="pinned versions"):
        verify_script._versions_from_environment(load_manifests(ROOT))


def test_deployment_receipt_uses_runtime_binding_order() -> None:
    assert (
        verify_script.deployment_receipt(
            "https://example.services.ai.azure.com/api/projects/demo",
            (
                ("supply-response-signal", "11"),
                ("supply-response-context", "12"),
                ("supply-response-decision", "13"),
            ),
        )
        == "0bdb068692b0d82bdfd563adad8a8c1ed249669e9b6fbe7fcad6b7566c1f7778"
    )


@pytest.mark.parametrize(
    "versions",
    (
        (
            ("supply-response-context", "12"),
            ("supply-response-signal", "11"),
            ("supply-response-decision", "13"),
        ),
        (
            ("signal", "11"),
            ("context", "12"),
            ("decision", "13"),
        ),
    ),
)
def test_deployment_receipt_rejects_noncanonical_agent_name_order(
    versions: tuple[tuple[str, str], ...],
) -> None:
    with pytest.raises(ValueError, match="names"):
        verify_script.deployment_receipt(
            "https://example.services.ai.azure.com/api/projects/demo",
            versions,
        )


@pytest.mark.parametrize("version", ("0", "01", "١", "12345678901", 7))
def test_deployment_receipt_rejects_invalid_pinned_version(version: object) -> None:
    with pytest.raises((TypeError, ValueError), match="version"):
        verify_script.deployment_receipt(
            "https://example.services.ai.azure.com/api/projects/demo",
            (
                ("supply-response-signal", cast(Any, version)),
                ("supply-response-context", "12"),
                ("supply-response-decision", "13"),
            ),
        )


def test_deployment_receipt_rejects_untrusted_project_endpoint() -> None:
    with pytest.raises(ValueError, match="trusted"):
        verify_script.deployment_receipt(
            "https://example.invalid/api/projects/demo",
            (
                ("supply-response-signal", "11"),
                ("supply-response-context", "12"),
                ("supply-response-decision", "13"),
            ),
        )


def test_live_verify_emits_receipt_after_all_exact_remote_checks(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    endpoint = "https://example.services.ai.azure.com/api/projects/demo"
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    project = FakeProject()
    _set_exact_remote_versions(project, versions_by_role)
    _set_foundry_binding_environment(monkeypatch, versions_by_role, canonical=True)
    monkeypatch.setenv("SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT", endpoint)
    monkeypatch.setenv("SUPPLY_RESPONSE_ENTRA_TENANT_ID", "tenant")
    monkeypatch.setattr(sys, "argv", ["verify_foundry_agents.py", "--live"])
    monkeypatch.setattr(verify_script, "_live_project", lambda: project)

    assert verify_script.main() == 0

    output = capsys.readouterr().out.splitlines()
    assert set(output[:-1]) == {
        "supply-response-signal=11",
        "supply-response-context=12",
        "supply-response-decision=13",
    }
    assert output[-1] == (
        "SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT="
        "0bdb068692b0d82bdfd563adad8a8c1ed249669e9b6fbe7fcad6b7566c1f7778"
    )


def test_live_verify_emits_no_receipt_when_a_remote_field_drifts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    versions_by_role = {"signal": "11", "context": "12", "decision": "13"}
    project = FakeProject()
    _set_exact_remote_versions(project, versions_by_role)
    signal = next(item for item in load_manifests(ROOT) if item.role == "signal")
    cast(
        Any, project.agents.remote[(signal.agent_name, versions_by_role["signal"])]
    ).description = "remote drift"
    _set_foundry_binding_environment(monkeypatch, versions_by_role, canonical=True)
    monkeypatch.setenv(
        "SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("SUPPLY_RESPONSE_ENTRA_TENANT_ID", "tenant")
    monkeypatch.setattr(sys, "argv", ["verify_foundry_agents.py", "--live"])
    monkeypatch.setattr(verify_script, "_live_project", lambda: project)

    with pytest.raises(RuntimeError, match="drift"):
        verify_script.main()

    assert "SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT" not in capsys.readouterr().out


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
        monkeypatch.setenv(f"{prefix}_AGENT_NAME", item.agent_name)
        monkeypatch.delenv(f"{prefix}_AGENT_VERSION", raising=False)

    constructed = False

    def forbidden_project():
        nonlocal constructed
        constructed = True
        raise AssertionError("credential/client construction occurred")

    monkeypatch.setattr(script, "_live_project", forbidden_project)
    with pytest.raises(SystemExit, match="pinned versions"):
        script.main()
    assert not constructed
