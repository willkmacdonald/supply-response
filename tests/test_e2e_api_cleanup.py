from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


VALID_NAME = "e2e-12345678-1234-4abc-8def-1234567890ab.db"


def _fake_repository(tmp_path: Path, *, symlink_tmp: bool = False) -> Path:
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    source = Path(__file__).parents[1] / "scripts" / "run_e2e_api.sh"
    target = scripts / source.name
    shutil.copy2(source, target)
    if symlink_tmp:
        escaped = tmp_path / "escaped-parent"
        escaped.mkdir()
        (repository / ".tmp").symlink_to(escaped, target_is_directory=True)
    else:
        (repository / ".tmp").mkdir()
    return repository


def _validate(script: Path, database_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script)],
        env={
            **os.environ,
            "SUPPLY_RESPONSE_E2E_DATABASE_PATH": str(database_path),
            "SUPPLY_RESPONSE_E2E_VALIDATE_ONLY": "true",
        },
        check=False,
        capture_output=True,
        text=True,
    )


def test_cleanup_validation_accepts_only_the_generated_database_shape(tmp_path):
    repository = _fake_repository(tmp_path)

    result = _validate(
        repository / "scripts/run_e2e_api.sh", repository / ".tmp" / VALID_NAME
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "case",
    [
        "traversal",
        "nested",
        "bad_basename",
        "symlink_parent",
        "outside_repository",
    ],
)
def test_cleanup_validation_rejects_unsafe_paths_without_deleting_sentinels(
    tmp_path,
    case,
):
    repository = _fake_repository(tmp_path, symlink_tmp=case == "symlink_parent")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("must remain", encoding="utf-8")
    temporary = repository / ".tmp"

    if case == "traversal":
        hop = temporary / "e2e-hop.db"
        hop.mkdir()
        (repository / "outside").mkdir()
        database_path = hop / ".." / ".." / "outside" / VALID_NAME
    elif case == "nested":
        nested = temporary / "e2e-nested"
        nested.mkdir()
        database_path = nested / VALID_NAME
    elif case == "bad_basename":
        database_path = temporary / VALID_NAME.replace(".db", "Xdb")
    elif case == "symlink_parent":
        database_path = temporary / VALID_NAME
    else:
        database_path = outside / VALID_NAME
    database_path.write_text("target must remain", encoding="utf-8")

    result = _validate(repository / "scripts/run_e2e_api.sh", database_path)

    assert result.returncode == 2
    assert "Refusing to use an unrecognized E2E database path." in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "must remain"
    assert database_path.read_text(encoding="utf-8") == "target must remain"
