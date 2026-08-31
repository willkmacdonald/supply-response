from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Protocol


class CitationNavigationError(RuntimeError):
    """An authenticated citation did not resolve to a trusted artifact view."""


class AuthenticatedCitationVerifier(Protocol):
    async def verify(self, urls: Sequence[str]) -> None: ...


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

    async def verify(self, urls: Sequence[str]) -> None:
        if not urls:
            raise CitationNavigationError("at least one citation URL is required")
        for url in urls:
            output = await self._runner(
                "node",
                str(self._script),
                str(self._storage_state_path),
                self._tenant_sharepoint_host,
                input_text=json.dumps({"url": url}),
            )
            try:
                result = json.loads(output)
            except json.JSONDecodeError as error:
                raise CitationNavigationError(
                    "authenticated citation verifier returned malformed output"
                ) from error
            if not isinstance(result, dict) or result.get("ok") is not True:
                raise CitationNavigationError(
                    "citation did not resolve to an authenticated trusted artifact"
                )
