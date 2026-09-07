"""The approved one-shot inspection must not leave a capture facility installed."""

from importlib.util import find_spec
from pathlib import Path


def test_temporary_capture_is_removed_from_runtime():
    assert find_spec("integrations.workiq.memory_capture") is None
    root = Path(__file__).resolve().parents[2]
    for relative in ("apps/api/app/main.py", "integrations/workiq/client.py"):
        assert "memory_capture" not in (root / relative).read_text()
        assert "_send_captured" not in (root / relative).read_text()
