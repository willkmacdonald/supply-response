from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class CitationNavigationError(RuntimeError):
    """An authenticated citation did not resolve to a trusted artifact view."""


@dataclass(frozen=True)
class CitationExpectation:
    url: str
    expected_excerpt: str
    source_identity: str


class AuthenticatedCitationVerifier(Protocol):
    async def verify(self, citations: Sequence[CitationExpectation]) -> None: ...


Runner = Callable[..., Awaitable[str]]


async def _run_node(*args: str, input_text: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input_text.encode())
    if process.returncode != 0:
        detail = stderr.decode(errors="replace")[:512]
        raise CitationNavigationError(
            f"authenticated citation verifier failed: {detail}"
        )
    return stdout.decode()


class PlaywrightCitationVerifier:
    """Verify citations in Alex's authenticated Playwright storage state."""

    def __init__(
        self,
        *,
        storage_state_path: Path,
        tenant_sharepoint_host: str,
        runner: Runner = _run_node,
    ) -> None:
        self._storage_state_path = storage_state_path
        self._tenant_sharepoint_host = tenant_sharepoint_host
        self._runner = runner
        self._script = (
            Path(__file__).resolve().parents[2]
            / "apps"
            / "web"
            / "scripts"
            / "verify-workiq-citations.mjs"
        )

    async def verify(self, citations: Sequence[CitationExpectation]) -> None:
        if not citations:
            raise CitationNavigationError("at least one citation URL is required")
        for citation in citations:
            if (
                not isinstance(citation, CitationExpectation)
                or not citation.url.strip()
                or len(citation.expected_excerpt.strip()) < 24
                or not citation.source_identity.strip()
            ):
                raise CitationNavigationError(
                    "citation expectation is incomplete or ambiguous"
                )
            output = await self._runner(
                "node",
                str(self._script),
                str(self._storage_state_path),
                self._tenant_sharepoint_host,
                input_text=json.dumps(
                    {
                        "url": citation.url,
                        "expectedExcerpt": citation.expected_excerpt,
                        "sourceIdentity": citation.source_identity,
                    }
                ),
            )
            try:
                result = json.loads(output)
            except json.JSONDecodeError as error:
                raise CitationNavigationError(
                    "authenticated citation verifier returned malformed output"
                ) from error
            if (
                not isinstance(result, dict)
                or result.get("ok") is not True
                or result.get("sourceIdentity") != citation.source_identity
            ):
                raise CitationNavigationError(
                    "citation did not resolve to an authenticated trusted artifact"
                )
