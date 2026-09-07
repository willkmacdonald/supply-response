"""TEMPORARY one-pair operator capture. No HTTP route, files, or logging.

Remove this module and its two integration hooks after the approved inspection.
The Linux abstract socket is reachable only inside the container's network
namespace; SO_PEERCRED additionally restricts it to the application uid.
"""

from __future__ import annotations

import json
import os
import re
import socket
import struct
import sys
import time
from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import Any

SOCKET_ADDRESS = "\0supply-response-workiq-capture-v1"
_REFERENCE_TYPE = "application/vnd.ms-workiq-reference"
_FIELDS = frozenset(
    {
        "targetLink",
        "webUrl",
        "url",
        "sourceId",
        "sourceType",
        "sourceTimestamp",
        "excerpt",
        "title",
        "isCitedInResponse",
        "isSourceFiltered",
    }
)


def _text(value: str, limit: int = 8192) -> str:
    value = value[:limit]
    value = re.sub(r"(?i)Bearer\s+[^\s\"<>]+", "Bearer [REDACTED]", value)
    value = re.sub(
        r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED]", value
    )
    return re.sub(
        r"(?i)([?&](?:access_token|id_token|refresh_token|token|sig|code|client_secret)=)[^\s&#\"<>]+",
        r"\1[REDACTED]",
        value,
    )


def project_answer(payload: Any) -> dict[str, Any]:
    try:
        artifacts = payload["result"]["task"]["artifacts"]
        if not isinstance(artifacts, list):
            raise TypeError
    except (KeyError, TypeError):
        return {"outcome": "invalid_artifacts"}
    result: dict[str, Any] = {
        "answers": [],
        "citations": [],
        "uninspected_data_parts": 0,
        "truncated": len(artifacts) > 4,
    }
    for artifact in artifacts[:4]:
        parts = artifact.get("parts", []) if isinstance(artifact, dict) else []
        if not isinstance(parts, list):
            continue
        result["truncated"] |= len(parts) > 8
        for part in parts[:8]:
            if not isinstance(part, dict):
                continue
            answer = part.get("text")
            if isinstance(answer, str):
                result["answers"].append(_text(answer))
                result["truncated"] |= len(answer) > 8192
            data = part.get("data")
            if data is None:
                continue
            if part.get("mediaType") != _REFERENCE_TYPE or not isinstance(data, dict):
                result["uninspected_data_parts"] += 1
                continue
            references = {}
            result["truncated"] |= len(data) > 16
            for key, reference in list(data.items())[:16]:
                if not isinstance(key, str) or not isinstance(reference, dict):
                    continue
                fields = {}
                for field in sorted(_FIELDS):
                    value = reference.get(field)
                    if isinstance(value, str):
                        fields[field] = _text(value, 2048)
                        result["truncated"] |= len(value) > 2048
                    elif isinstance(value, bool):
                        fields[field] = value
                if fields:
                    references[_text(key, 128)] = fields
            result["citations"].append(references)
    if len(json.dumps(result).encode()) > 65536:
        return {"outcome": "projection_limit", "truncated": True}
    return result


class MemoryCapture:
    def __init__(self, *, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._lock = Lock()
        self._state = "disabled"
        self._deadline = 0.0
        self._pair: tuple[str, str] | None = None
        self._tickets: dict[object, str] = {}
        self._responses: dict[str, Any] = {}

    def _clear(self) -> None:
        self._state = "spent"
        self._pair = None
        self._tickets.clear()
        self._responses.clear()

    def _expire(self) -> None:
        if (
            self._state in {"armed", "collecting", "ready"}
            and self._now() >= self._deadline
        ):
            self._clear()

    def expire(self) -> None:
        with self._lock:
            self._expire()

    def command(self, command: str) -> dict[str, Any]:
        with self._lock:
            self._expire()
            if command == "arm" and self._state == "disabled":
                self._state = "armed"
                self._deadline = self._now() + 1800
            elif command == "discard":
                self._clear()
            elif command == "take" and self._state == "ready":
                responses = dict(self._responses)
                self._clear()
                return {"state": "spent", "responses": responses}
            elif command not in {"arm", "status", "take"}:
                return {"state": "invalid_command"}
            return {"state": self._state}

    def reserve(self, kind: str, case_id: str, analysis_id: str) -> object | None:
        with self._lock:
            self._expire()
            if self._state not in {"armed", "collecting"} or kind not in {
                "supplier",
                "quality",
            }:
                return None
            pair = (case_id, analysis_id)
            if self._pair is None:
                self._pair = pair
                self._state = "collecting"
                self._deadline = min(self._deadline, self._now() + 600)
            if self._pair != pair or kind in self._tickets.values():
                return None
            ticket = object()
            self._tickets[ticket] = kind
            return ticket

    def record(self, ticket: object | None, payload: Any) -> None:
        with self._lock:
            self._expire()
            kind = self._tickets.get(ticket)
            if self._state != "collecting" or kind is None or kind in self._responses:
                return
            try:
                self._responses[kind] = project_answer(payload)
            except Exception:  # noqa: BLE001 - never log or propagate private projection errors
                self._responses[kind] = {"outcome": "projection_failed"}
            if len(self._responses) == 2:
                self._state = "ready"

    def failed(self, ticket: object | None) -> None:
        with self._lock:
            self._expire()
            kind = self._tickets.get(ticket)
            if (
                self._state == "collecting"
                and kind is not None
                and kind not in self._responses
            ):
                self._responses[kind] = {"outcome": "unavailable"}
                if len(self._responses) == 2:
                    self._state = "ready"


capture = MemoryCapture()


def peer_allowed(peer_uid: int, app_uid: int) -> bool:
    return peer_uid == app_uid


def start_operator_capture() -> Callable[[], None]:
    """Start only on Linux; fail closed without impacting application startup."""
    if sys.platform != "linux":
        return lambda: None
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(SOCKET_ADDRESS)
        listener.listen(1)
        listener.settimeout(1)
    except OSError:
        listener.close()
        return lambda: None
    stopped = Event()

    def serve() -> None:
        while not stopped.is_set():
            capture.expire()
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with connection:
                try:
                    connection.settimeout(1)
                    _, uid, _ = struct.unpack(
                        "3i",
                        connection.getsockopt(
                            socket.SOL_SOCKET, socket.SO_PEERCRED, 12
                        ),
                    )
                    if not peer_allowed(uid, os.geteuid()):
                        continue
                    command = connection.recv(32).decode("ascii").strip()
                    output = json.dumps(capture.command(command)).encode()
                    connection.sendall(output)
                except (OSError, ValueError, UnicodeError):
                    pass
                finally:
                    # Do not retain a serialized take result across accept timeouts.
                    output = b""

    thread = Thread(target=serve, name="temporary-workiq-capture", daemon=True)
    thread.start()

    def stop() -> None:
        stopped.set()
        listener.close()
        thread.join(timeout=2)
        capture.command("discard")

    return stop


def operator_command(command: str) -> None:
    """Container-exec stdout only. Never run via a file-capturing shell wrapper."""
    if command not in {"arm", "status", "take", "discard"}:
        raise SystemExit("invalid command")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect(SOCKET_ADDRESS)
        connection.sendall(command.encode("ascii"))
        chunks = []
        size = 0
        while chunk := connection.recv(8192):
            size += len(chunk)
            if size > 140000:
                raise SystemExit("capture exceeds operator limit")
            chunks.append(chunk)
        print(b"".join(chunks).decode("utf-8"))


if __name__ == "__main__":
    operator_command(sys.argv[1] if len(sys.argv) == 2 else "invalid")
