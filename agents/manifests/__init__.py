from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_NAME = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_EXPECTED_ROLES = {"signal", "context", "decision"}
_EXPECTED_INSTRUCTIONS = {
    "signal": Path("agents/signal/instructions.md"),
    "context": Path("agents/context/instructions.md"),
    "decision": Path("agents/decision/instructions.md"),
}


class ManifestError(ValueError):
    pass


class _ManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_name: str
    model: str
    instructions_path: str
    description: str = Field(min_length=8, max_length=1_024)
    tools: tuple[object, ...]

    @field_validator("agent_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not _NAME.fullmatch(value):
            raise ValueError("agent name is outside the trusted naming policy")
        return value

    @field_validator("model")
    @classmethod
    def valid_model(cls, value: str) -> str:
        if not _MODEL.fullmatch(value) or value.lower() == "latest":
            raise ValueError("model deployment name is outside the trusted policy")
        return value

    @field_validator("tools")
    @classmethod
    def no_tools(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if value:
            raise ValueError("prompt agents must not expose model-visible tools")
        return value


class AgentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    role: str
    agent_name: str
    model: str
    instructions_path: Path
    instructions: str
    instructions_sha256: str
    description: str
    tools: tuple[object, ...] = ()


def load_manifests(root: Path) -> tuple[AgentManifest, ...]:
    root = root.resolve()
    manifest_candidate = root / "agents" / "manifests"
    try:
        manifest_dir = manifest_candidate.resolve(strict=True)
    except OSError as exc:
        raise ManifestError("agent manifest directory validation failed") from exc
    if (
        manifest_candidate.is_symlink()
        or manifest_dir != manifest_candidate
        or not manifest_dir.is_dir()
        or not manifest_dir.is_relative_to(root)
    ):
        raise ManifestError("agent manifest directory is outside the frozen location")
    paths = sorted(manifest_dir.glob("*.json"))
    roles = {path.stem for path in paths}
    if roles != _EXPECTED_ROLES or len(paths) != 3:
        raise ManifestError(
            "exactly the signal, context, and decision manifests are required"
        )
    loaded: list[AgentManifest] = []
    try:
        for path in paths:
            if path.is_symlink() or path.resolve(strict=True).parent != manifest_dir:
                raise ManifestError("agent manifest file is not a frozen regular file")
            document = _ManifestDocument.model_validate_json(path.read_text("utf-8"))
            relative = Path(document.instructions_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ManifestError("instructions path must be repository-relative")
            if relative != _EXPECTED_INSTRUCTIONS[path.stem]:
                raise ManifestError("agent role instruction path contains drift")
            resolved = (root / relative).resolve(strict=True)
            if not resolved.is_relative_to(root) or resolved.is_symlink():
                raise ManifestError("instructions path escapes the repository")
            instructions = resolved.read_text("utf-8")
            encoded = instructions.encode("utf-8")
            if len(encoded) < 100 or len(encoded) > 16_000 or "\x00" in instructions:
                raise ManifestError("instructions are malformed or outside size limits")
            loaded.append(
                AgentManifest(
                    role=path.stem,
                    agent_name=document.agent_name,
                    model=document.model,
                    instructions_path=resolved,
                    instructions=instructions,
                    instructions_sha256=hashlib.sha256(encoded).hexdigest(),
                    description=document.description,
                    tools=document.tools,
                )
            )
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ManifestError("agent manifest validation failed") from exc
    names = [item.agent_name for item in loaded]
    if len(names) != len(set(names)):
        raise ManifestError("agent names must be unique")
    return tuple(loaded)
