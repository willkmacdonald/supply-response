import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "Supply-Response-Project-Brief.md"
EVALUATION_CASES = ROOT / "evaluations/datasets/evaluation_cases.json"


def test_project_brief_preserves_core_requirements():
    text = BRIEF.read_text(encoding="utf-8")
    assert "## Acceptance criteria" in text
    assert "## Evaluation cases" in text
    assert "Scenario 5 must be marked **not executable**" in text
    assert "The prototype must not create a real PO or financial commitment." in text


def test_evaluation_catalog_is_complete_and_linked_to_tests():
    payload = json.loads(EVALUATION_CASES.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert payload["version"] == "1.0.0"
    assert [case["id"] for case in cases] == [
        f"RL-EVAL-{index:03d}" for index in range(1, 11)
    ]

    required_keys = {"id", "name", "input", "expected", "test"}
    for case in cases:
        assert set(case) == required_keys
        test_path, test_name = case["test"].split("::", maxsplit=1)
        source = (ROOT / test_path).read_text(encoding="utf-8")
        assert f"def {test_name}(" in source, case["id"]
