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
    ) -> None:
        self._services = services
        self._poll_interval_seconds = poll_interval_seconds
        self._stop = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None
        self._playback_tasks: dict[str, asyncio.Task[None]] = {}
        self._failed_playbacks: set[str] = set()

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
            if (
                playback_id in self._playback_tasks
                or playback_id in self._failed_playbacks
            ):
                continue
            self._playback_tasks[playback_id] = asyncio.create_task(
                self._run_playback(playback_id),
                name=f"supply-response-playback-{playback_id}",
            )

    async def _run_playback(self, playback_id: str) -> None:
        try:
            await asyncio.to_thread(
                self._services.playback_service.run_to_completion,
                playback_id,
            )
        except PlaybackInterrupted:
            return
        except Exception:
            self._failed_playbacks.add(playback_id)
            logger.exception(
                "playback progression failed",
                extra={"playback_id": playback_id},
            )
        finally:
            self._playback_tasks.pop(playback_id, None)
