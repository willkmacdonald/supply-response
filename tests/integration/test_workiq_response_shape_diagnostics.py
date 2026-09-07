from __future__ import annotations

import inspect
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from data.domain.evidence import AuthorityScope, EvidenceKind, EvidenceRequirement
from integrations.workiq import diagnostics
from integrations.workiq.diagnostics import log_response_shape, response_shape
from integrations.workiq.errors import WorkIQProtocolError
from integrations.workiq.normalizer import normalize_a2a_evidence

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures" / "workiq"
NOW = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def reset_response_shape_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "_emitted_source_kinds", set())


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def _normalize(
    payload: dict[str, Any],
    *,
    expected_source_id: str = "fixture-source-alpha",
    expected_authority_scope: AuthorityScope = AuthorityScope.SUPPLIER_STATEMENT,
):
    return normalize_a2a_evidence(
        payload,
        case_id="case",
        analysis_id="analysis",
        retrieved_at=NOW,
        expected_source_id=expected_source_id,
        expected_authority_scope=expected_authority_scope,
        tenant_sharepoint_host="tenant.sharepoint.com",
    )


def _diagnostic_records(
    caplog: pytest.LogCaptureFixture,
) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "integrations.workiq.diagnostics"
    ]


def test_shape_never_copies_scalar_values_or_unknown_keys() -> None:
    result = response_shape(
        {
            "text": "secret-value",
            "secret-key": {"url": "secret-url"},
            "id": 987654,
            "isCitedInResponse": True,
            "value": None,
        }
    )

    assert "secret" not in result
    assert "987654" not in result
    assert '"text":"string"' in result
    assert '"id":"number"' in result
    assert '"isCitedInResponse":"boolean"' in result
    assert '"value":"null"' in result


def test_shape_retains_only_approved_names_in_nested_reference_maps() -> None:
    shape = json.loads(
        response_shape(
            {
                "metadata": {
                    "private-map-key": {
                        "references": [
                            {
                                "private-reference-key": {
                                    "sourceId": "private-source-id",
                                    "targetLink": "https://private.invalid/item",
                                }
                            }
                        ]
                    }
                }
            }
        )
    )
    serialized = json.dumps(shape, separators=(",", ":"))

    assert "private" not in serialized
    assert "references" in serialized
    assert "sourceId" in serialized
    assert "targetLink" in serialized


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("private", "string"),
        (42, "number"),
        (2.5, "number"),
        (True, "boolean"),
        (False, "boolean"),
        (None, "null"),
        (b"private", "other"),
    ],
)
def test_shape_labels_scalar_types_without_values(value: object, expected: str) -> None:
    assert response_shape(value) == json.dumps(expected)


def test_shape_does_not_parse_json_looking_text() -> None:
    secret_json = '{"facts":[{"claim":"private-json-claim"}]}'

    assert response_shape({"text": secret_json}) == (
        '{"type":"object","count":1,"fields":{"text":"string"}}'
    )


def test_shape_bounds_cyclic_deep_and_wide_inputs() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    deep: object = "private-deep-value"
    for _ in range(40):
        deep = {"data": deep}
    wide = [{"claim": f"private-{index}"} for index in range(300)]

    for value in (cyclic, deep, wide):
        result = response_shape(value)
        parsed = json.loads(result)
        assert parsed is not None
        assert "private" not in result
        assert len(result) <= 8_192
        assert "truncated" in result

    wide_shape = json.loads(response_shape(wide))
    assert len(wide_shape["items"]) == 2


def test_shape_depth_limit_allows_level_twelve_and_truncates_level_thirteen() -> None:
    def nested_data(levels: int) -> object:
        value: object = "private-value"
        for _ in range(levels):
            value = {"data": value}
        return value

    def descend_data(shape: object, levels: int) -> object:
        current = shape
        for _ in range(levels):
            assert isinstance(current, dict)
            current = current["fields"]["data"]
        return current

    level_twelve = json.loads(response_shape(nested_data(11)))
    level_thirteen = json.loads(response_shape(nested_data(12)))

    assert descend_data(level_twelve, 11) == "string"
    assert descend_data(level_thirteen, 12) == {"type": "truncated"}


def test_shape_shared_budget_visits_exactly_128_nodes() -> None:
    outer_fields = (
        "result",
        "task",
        "artifacts",
        "parts",
        "data",
        "facts",
        "citation",
        "citations",
    )
    inner_fields = (
        "result",
        "task",
        "artifacts",
        "parts",
        "data",
        "facts",
        "citation",
        "citations",
        "citationMap",
        "references",
        "reference",
        "sources",
        "source",
        "sourceId",
        "sourceType",
    )
    payload = {
        outer_key: {inner_key: "private-value" for inner_key in inner_fields}
        for outer_key in outer_fields
    }

    shape = json.loads(response_shape(payload))
    final_branch = shape["fields"]["citations"]["fields"]

    assert final_branch["sourceId"] == "string"
    assert final_branch["sourceType"] == {"type": "truncated"}


def test_shape_keeps_exactly_two_array_and_unknown_key_examples() -> None:
    assert response_shape(["private-one", "private-two", "private-three"]) == (
        '{"type":"array","count":3,"items":["string","string"],"truncated":true}'
    )

    unknown_shape = json.loads(
        response_shape(
            {
                "private-one": {"text": "private-value-one"},
                "private-two": {"text": "private-value-two"},
                "private-three": {"text": "private-value-three"},
            }
        )
    )

    assert unknown_shape == {
        "type": "object",
        "count": 3,
        "unknown": [
            {"type": "object", "count": 1, "fields": {"text": "string"}},
            {"type": "object", "count": 1, "fields": {"text": "string"}},
        ],
        "truncated": True,
    }
    assert "private" not in json.dumps(unknown_shape)


def test_shape_over_8192_characters_uses_exact_fixed_fallback() -> None:
    fields = (
        "result",
        "contextId",
        "isCitedInResponse",
        "sourceTimestamp",
        "authorityScope",
        "citationMap",
        "references",
        "artifactId",
        "description",
        "effectiveAt",
        "expiresAt",
        "targetLink",
        "sourceType",
        "sourceId",
        "mediaType",
        "metadata",
        "filename",
        "citations",
        "artifacts",
        "message",
        "content",
        "webUrl",
        "reference",
        "sources",
        "excerpt",
    )
    payload: object = "private-value"
    for _ in range(12):
        payload = {
            key: payload if key == "result" else "private-value" for key in fields
        }

    assert response_shape(payload) == '{"type":"truncated"}'


def test_shape_uses_shared_node_budget_and_prioritizes_evidence_paths() -> None:
    noisy_fields = (
        "id",
        "contextId",
        "status",
        "state",
        "message",
        "name",
        "description",
        "metadata",
        "mediaType",
        "raw",
        "filename",
        "effectiveAt",
        "expiresAt",
        "title",
        "index",
    )
    budget_tree = {
        key: {nested_key: "private-value" for nested_key in noisy_fields}
        for key in noisy_fields
    }
    budget_shape = response_shape(budget_tree)

    assert '"fields"' in budget_shape
    assert '"type":"truncated"' in budget_shape
    assert "private" not in budget_shape

    payload = {
        "result": {
            "task": {
                "status": budget_tree,
                "message": budget_tree,
                "metadata": budget_tree,
                "artifacts": [
                    {
                        "parts": [
                            {
                                "data": {
                                    "facts": [
                                        {"citation": {"sourceId": "private-source-id"}}
                                    ]
                                }
                            }
                        ]
                    }
                ],
            }
        }
    }
    shape = json.loads(response_shape(payload))

    source_id_shape = shape["fields"]["result"]["fields"]["task"]["fields"][
        "artifacts"
    ]["items"][0]["fields"]["parts"]["items"][0]["fields"]["data"]["fields"]["facts"][
        "items"
    ][0]["fields"]["citation"]["fields"]["sourceId"]
    assert source_id_shape == "string"


@pytest.mark.parametrize(
    ("fixture_name", "source_id", "scope"),
    [
        (
            "supplier-alpha-a2a.json",
            "fixture-source-alpha",
            AuthorityScope.SUPPLIER_STATEMENT,
        ),
        (
            "supplier-beta-quality-a2a.json",
            "fixture-source-beta-quality",
            AuthorityScope.COLLABORATION_STATEMENT,
        ),
    ],
)
def test_successful_fixture_normalization_emits_no_shape_diagnostic(
    fixture_name: str,
    source_id: str,
    scope: AuthorityScope,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="integrations.workiq.diagnostics"):
        retrieval = _normalize(
            _fixture(fixture_name),
            expected_source_id=source_id,
            expected_authority_scope=scope,
        )

    assert retrieval.evidence
    assert _diagnostic_records(caplog) == []


def test_rejected_evidence_remains_contextual_without_failure_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = _fixture("supplier-alpha-a2a.json")
    fact = payload["result"]["task"]["artifacts"][0]["parts"][0]["data"]["facts"][0]
    fact["citation"]["sourceId"] = "wrong-source"

    with caplog.at_level(logging.WARNING, logger="integrations.workiq.diagnostics"):
        item = _normalize(payload).evidence[0]

    assert item.kind is EvidenceKind.CONTEXTUAL_EVIDENCE
    assert item.requirement is EvidenceRequirement.CONTEXTUAL
    assert _diagnostic_records(caplog) == []


@pytest.mark.parametrize(
    ("scope", "expected_source_kind"),
    [
        (AuthorityScope.SUPPLIER_STATEMENT, "supplier"),
        (AuthorityScope.COLLABORATION_STATEMENT, "quality"),
        (AuthorityScope.OPERATIONAL_DATE, "other"),
        ("supplier_statement", "other"),
    ],
)
def test_normalization_failure_logs_exact_fixed_source_kind(
    scope: Any,
    expected_source_kind: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = {"result": {"private-key": "private-value"}}

    with (
        caplog.at_level(logging.WARNING, logger="integrations.workiq.diagnostics"),
        pytest.raises(WorkIQProtocolError, match="Work IQ task is missing"),
    ):
        _normalize(payload, expected_authority_scope=scope)

    records = _diagnostic_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.getMessage().startswith(
        f"workiq_response_shape source={expected_source_kind} shape="
    )
    assert isinstance(record.args, tuple)
    assert record.args[0] == expected_source_kind
    assert "private" not in repr(record.__dict__)
    assert record.exc_info is None
    assert record.stack_info is None


def test_repeated_same_source_failures_emit_one_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="integrations.workiq.diagnostics"):
        for _ in range(2):
            with pytest.raises(WorkIQProtocolError, match="Work IQ result is missing"):
                _normalize({})

    assert len(_diagnostic_records(caplog)) == 1


def test_log_helper_normalizes_unapproved_source_label(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="integrations.workiq.diagnostics"):
        log_response_shape({"text": "private"}, "private-source-label")

    record = _diagnostic_records(caplog)[0]
    assert isinstance(record.args, tuple)
    assert record.args[0] == "other"
    assert "private" not in repr(record.__dict__)


def test_diagnostic_failure_does_not_mask_original_normalization_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_error = WorkIQProtocolError("original normalizer failure")

    def fail_normalization(*args: Any, **kwargs: Any) -> None:
        raise original_error

    def fail_diagnostic(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("diagnostic failure")

    monkeypatch.setattr(
        "integrations.workiq.normalizer._normalize_a2a_evidence", fail_normalization
    )
    monkeypatch.setattr(
        "integrations.workiq.normalizer.log_response_shape", fail_diagnostic
    )

    with pytest.raises(WorkIQProtocolError) as caught:
        _normalize({})

    assert caught.value is original_error


def test_public_normalizer_signature_remains_explicit() -> None:
    signature = inspect.signature(normalize_a2a_evidence)

    assert tuple(signature.parameters) == (
        "payload",
        "case_id",
        "analysis_id",
        "retrieved_at",
        "expected_source_id",
        "expected_authority_scope",
        "tenant_sharepoint_host",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in tuple(signature.parameters.values())[1:]
    )
