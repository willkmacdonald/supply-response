from __future__ import annotations

import asyncio
import logging

from apps.api.app.dependencies import ApplicationServices
from services.execution.playback import PlaybackInterrupted

logger = logging.getLogger(__name__)


class RuntimeProgression:
    """Advance persisted runtime work while the composed API is alive."""

    def __init__(
        self,
        services: ApplicationServices,
        *,
        poll_interval_seconds: float = 0.25,
        playback_max_attempts: int = 3,
    ) -> None:
        self._services = services
        self._poll_interval_seconds = poll_interval_seconds
        self._stop = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None
        self._playback_tasks: dict[str, asyncio.Task[None]] = {}
        if playback_max_attempts < 1:
            raise ValueError("playback retry attempts must be positive")
        self._playback_max_attempts = playback_max_attempts
        self._playback_failures: dict[str, int] = {}

    async def start(self) -> None:
        reset = getattr(self._services.playback_clock, "reset", None)
        if reset is not None:
            reset()
        self._loop_task = asyncio.create_task(
            self._run(),
            name="supply-response-runtime-progression",
        )

    async def stop(self) -> None:
        self._stop.set()
        stop = getattr(self._services.playback_clock, "stop", None)
        if stop is not None:
            stop()
        if self._loop_task is not None:
            await self._loop_task

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(),
                        timeout=self._poll_interval_seconds,
                    )
                except TimeoutError:
                    await self._advance_planning()
                    await self._start_persisted_playbacks()
        finally:
            if self._playback_tasks:
                await asyncio.gather(
                    *self._playback_tasks.values(),
                    return_exceptions=True,
                )

    async def _advance_planning(self) -> None:
        while await asyncio.to_thread(
            self._services.planning_worker.process_next_unattempted_outbox
        ):
            pass

    async def _start_persisted_playbacks(self) -> None:
        playback_ids = await asyncio.to_thread(self._services.in_progress_playback_ids)
        for playback_id in playback_ids:
            if playback_id in self._playback_tasks:
                continue
            self._playback_tasks[playback_id] = asyncio.create_task(
                self._run_playback(playback_id),
                name=f"supply-response-playback-{playback_id}",
            )

    async def _run_playback(self, playback_id: str) -> None:
        try:
            completed = await asyncio.to_thread(
                self._services.playback_service.run_to_completion,
                playback_id,
            )
            if completed.status.value != "in_progress":
                self._playback_failures.pop(playback_id, None)
        except PlaybackInterrupted:
            return
        except Exception:
            failures = self._playback_failures.get(playback_id, 0) + 1
            self._playback_failures[playback_id] = failures
            logger.exception(
                "playback progression failed",
                extra={"playback_id": playback_id, "attempt": failures},
            )
            if failures >= self._playback_max_attempts:
                try:
                    await asyncio.to_thread(
                        self._services.playback_service.record_failure,
                        playback_id,
                    )
                    self._playback_failures.pop(playback_id, None)
                except Exception:
                    logger.exception(
                        "playback terminal failure could not be recorded",
                        extra={"playback_id": playback_id},
                    )
        finally:
            self._playback_tasks.pop(playback_id, None)
