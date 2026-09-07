"""Stdlib-only Linux test; run in an isolated container, never against live data."""

import json
import runpy
import socket
import sys
import threading

module = runpy.run_path("integrations/workiq/memory_capture.py")
SOCKET_ADDRESS = module["SOCKET_ADDRESS"]
capture = module["capture"]
start_operator_capture = module["start_operator_capture"]


def call(command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect(SOCKET_ADDRESS)
        connection.sendall(command.encode())
        chunks = []
        while chunk := connection.recv(8192):
            chunks.append(chunk)
        return json.loads(b"".join(chunks))


stop = start_operator_capture()
try:
    assert call("status") == {"state": "disabled"}
    assert call("arm") == {"state": "armed"}
    body = {"result": {"task": {"artifacts": [{"parts": [{"text": "synthetic"}]}]}}}
    for kind in ("supplier", "quality"):
        capture.record(capture.reserve(kind, "case", "analysis"), body)
    assert call("status") == {"state": "ready"}
    assert len(call("take")["responses"]) == 2
    for thread in threading.enumerate():
        if thread.name == "temporary-workiq-capture":
            frame = sys._current_frames()[thread.ident]
            while frame:
                if frame.f_code.co_name == "serve":
                    assert not frame.f_locals.get("output"), (
                        "read response retained in server loop"
                    )
                frame = frame.f_back
    assert call("take") == {"state": "spent"}
    assert call("arm") == {"state": "spent"}
finally:
    stop()
try:
    call("status")
except OSError:
    print(
        "PASS: Linux abstract-socket lifecycle, one-shot capture and destructive read"
    )
else:
    raise AssertionError("socket remains open after shutdown")
