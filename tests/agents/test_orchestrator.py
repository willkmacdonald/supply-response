from __future__ import annotations

import asyncio
import gc
import traceback
import types
import weakref
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from agents.orchestrator.contracts import (
    AgentExplanationUnavailable,
    AnalyzeCommand,
    PartialDeterministicResult,
)
from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import Orchestrator, _evidence_payload, _scrub
from data.domain import CasePurpose, RuntimeMode
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.domain.evidence import AuthorityScope
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case

NOW = datetime(2026, 8, 30, 15, tzinfo=UTC)


def command() -> AnalyzeCommand:
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-AGENT-001",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    deterministic = AnalyzeCaseCommand(
        analysis_id="RL-ANALYSIS-AGENT-001",
        case=case,
        corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(
            snapshot,
            analysis_id="RL-ANALYSIS-AGENT-001",
            retrieved_at=NOW,
        ),
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=NOW,
        created_at=NOW,
        calculation_version="rl001-options-v1",
    )
    return AnalyzeCommand(deterministic=deterministic)


class FakeAgent:
    def __init__(self, response: dict[str, Any] | BaseException) -> None:
        self.response = response
        self.payloads: list[dict[str, Any]] = []

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def agents(
    *,
    signal: dict[str, Any] | BaseException | None = None,
    context: dict[str, Any] | BaseException | None = None,
    decision: dict[str, Any] | BaseException | None = None,
) -> tuple[Callable[[], LocalAgentSet], list[LocalAgentSet]]:
    made: list[LocalAgentSet] = []

    def factory() -> LocalAgentSet:
        result = LocalAgentSet(
            signal=FakeAgent(
                signal
                or {
                    "facts": [],
                    "uncertainties": [],
                }
            ),
            context=FakeAgent(
                context
                or {
                    "facts": [
                        {
                            "evidence_id": "RL-QUALITY-001",
                            "authority_scope": "qualification_state",
                            "source_span": "Beta qualification state is pending.",
                        }
                    ],
                    "uncertainties": [],
                }
            ),
            decision=FakeAgent(
                decision
                or {
                    "recommended_option_id": "RL-OPTION-COMBINED",
                    "stage_references": ["ranking-stage-1"],
                }
            ),
        )
        made.append(result)
        return result

    return factory, made


@pytest.mark.anyio
async def test_agent_disagreement_cannot_change_authoritative_analysis() -> None:
    factory, made = agents(
        decision={
            "recommended_option_id": "RL-OPTION-BETA",
            "stage_references": ["ranking-stage-1"],
        }
    )
    result = await Orchestrator(factory, analyze_case).analyze(command())

    assert result.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.decision_explanation is None
    assert result.explanation_status == "rejected"
    decision_payload = cast(FakeAgent, made[0].decision).payloads[0]
    assert decision_payload["recommended_option_id"] == "RL-OPTION-COMBINED"
    assert "operational_snapshot_json" not in decision_payload


@pytest.mark.anyio
async def test_agent_failure_preserves_token_free_deterministic_result() -> None:
    factory, _ = agents(context=TimeoutError("Bearer RL-TEST-SECRET"))

    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(factory, analyze_case).analyze(command())

    partial = caught.value.partial_result
    assert (
        partial.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    )
    assert partial.evidence_items
    assert "RL-TEST-SECRET" not in str(caught.value)
    assert "RL-TEST-SECRET" not in partial.model_dump_json()


@pytest.mark.anyio
async def test_model_payloads_are_minimized_bounded_and_identity_free() -> None:
    factory, made = agents()
    await Orchestrator(factory, analyze_case).analyze(command())

    context_payload = cast(FakeAgent, made[0].context).payloads[0]
    assert set(context_payload) == {"evidence"}
    serialized = str(context_payload)
    assert "bearer" not in serialized.lower()
    assert "upn" not in serialized.lower()
    assert "tenant" not in serialized.lower()
    assert "operational_snapshot" not in serialized
    assert len(serialized) < 16_000


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {"facts": [], "uncertainties": [], "tool_calls": ["danger"]},
        {
            "facts": [
                {
                    "evidence_id": "RL-QUALITY-001",
                    "authority_scope": "qualification_state",
                    "source_span": "x" * 5000,
                }
            ],
            "uncertainties": [],
        },
        {
            "facts": [
                {
                    "evidence_id": "RL-QUALITY-001",
                    "authority_scope": "qualification_state",
                    "source_span": "invented nonnumeric assertion",
                }
            ],
            "uncertainties": [],
        },
        {
            "facts": [
                {
                    "evidence_id": "RL-QUALITY-001",
                    "authority_scope": "supplier_statement",
                    "source_span": "Beta qualification state is pending.",
                }
            ],
            "uncertainties": [],
        },
        {
            "facts": [
                {
                    "evidence_id": "absent",
                    "authority_scope": "qualification_state",
                    "source_span": "Beta qualification state is pending.",
                }
            ],
            "uncertainties": [],
        },
    ],
)
async def test_untrusted_context_output_is_rejected(response: dict[str, Any]) -> None:
    factory, _ = agents(context=response)
    with pytest.raises(AgentExplanationUnavailable):
        await Orchestrator(factory, analyze_case).analyze(command())


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {
            "recommended_option_id": "rl-option-combined",
            "stage_references": ["ranking-stage-1"],
        },
        {"recommended_option_id": "combined", "stage_references": ["ranking-stage-1"]},
        {
            "recommended_option_id": "RL-OPTION-COMBINED",
            "stage_references": ["ranking-stage-99"],
        },
        {
            "recommended_option_id": "RL-OPTION-COMBINED",
            "stage_references": [],
            "explanation": "invented cause",
        },
    ],
)
async def test_untrusted_decision_output_is_rejected(response: dict[str, Any]) -> None:
    factory, _ = agents(decision=response)
    result = await Orchestrator(factory, analyze_case).analyze(command())
    assert result.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.decision_explanation is None
    assert result.explanation_status == "rejected"


@pytest.mark.anyio
async def test_empty_relevant_evidence_is_not_reported_as_available_extraction() -> (
    None
):
    factory, made = agents()
    result = await Orchestrator(factory, analyze_case).analyze(command())
    assert result.signal_extraction is None
    assert cast(FakeAgent, made[0].signal).payloads == []


@pytest.mark.anyio
async def test_final_model_boundary_rejects_credential_like_evidence() -> None:
    original = command()
    evidence = list(original.deterministic.evidence_items)
    secret = (
        "eyJhbGciOiJSUzI1NiJ9.eyJvaWQiOiJzZWNyZXQifQ.abcdefghijklmnopqrstuvwxyz012345"
    )
    evidence[-1] = evidence[-1].model_copy(
        update={
            "claim": f"Beta pending Bearer {secret}",
            "excerpt": f"Beta pending Bearer {secret}",
        }
    )
    contaminated = original.model_copy(
        update={
            "deterministic": original.deterministic.model_copy(
                update={"evidence_items": tuple(evidence)}
            )
        }
    )
    factory, made = agents()
    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(factory, analyze_case).analyze(contaminated)
    assert cast(FakeAgent, made[0].context).payloads == []
    assert secret not in caught.value.partial_result.model_dump_json()
    assert secret not in str(caught.value)


@pytest.mark.parametrize(
    "suspect",
    [
        "Bearer eyJhbGciOiJSUzI1NiJ9.eyJvaWQiOiIxMjM0NTY3OCJ9.abcdefghijklmnopqrstuvwxyz012345",
        "OBO assertion=eyJhbGciOiJSUzI1NiJ9.eyJ0aWQiOiIxMjM0NTY3OCJ9.abcdefghijklmnopqrstuvwxyz012345",
        "client_secret=fictional-but-confidential-value",
        "tenant_id=11111111-2222-3333-4444-555555555555",
        "oid is 11111111-2222-3333-4444-555555555555",
        "upn: alex@example.invalid",
        "https://example.invalid/evidence?access_token=credential",
        "https://user:password@example.invalid/evidence",
    ],
)
def test_final_prompt_dto_fails_closed_on_identity_or_credential_patterns(
    suspect: str,
) -> None:
    item = (
        command()
        .deterministic.evidence_items[-1]
        .model_copy(update={"claim": suspect, "excerpt": suspect})
    )
    with pytest.raises(ValueError, match="model data boundary"):
        _evidence_payload((item,), scopes={AuthorityScope.QUALIFICATION_STATE})


@pytest.mark.parametrize(
    "suspect",
    [
        "api_key=sk-realistic-api-key-value-1234567890",
        "API_KEY : 'sk-uppercase-key-value-1234567890'",
        "x-api-key: key-header-value-1234567890",
        "password = correct-horse-battery-staple",
        "PASSWD: another-confidential-password",
        "client_secret = tenant-client-secret-value",
        "secret: generic-assigned-secret-value",
        "token = opaque-service-token-value-1234567890",
        "Authorization: Basic dXNlcjpwYXNzd29yZA==",
        (
            "DefaultEndpointsProtocol=https;AccountName=demo;"
            "AccountKey=base64AccountKeyValue1234567890==;"
            "EndpointSuffix=core.windows.net"
        ),
        (
            "Endpoint=sb://demo.servicebus.windows.net/;"
            "SharedAccessKeyName=RootManageSharedAccessKey;"
            "SharedAccessKey=service-bus-key-value-1234567890="
        ),
        "Driver={ODBC Driver};Server=db.invalid;Uid=demo;Pwd=sql-password-value",
        "postgresql://demo:database-password-value@db.invalid/supply",
        (
            "SharedAccessSignature sr=https%3A%2F%2Fdemo.invalid&"
            "sig=signature-value-1234567890%3D&se=1893456000"
        ),
        (
            "https://demo.blob.core.windows.net/container?"
            "sv=2025-01-05&ss=b&srt=sco&sp=rwdlacupiytfx&se=2030-01-01&"
            "sig=sasSignatureValue1234567890%3D"
        ),
        (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC...\n"
            "-----END PRIVATE KEY-----"
        ),
        (
            "-----BEGIN%20RSA%20PRIVATE%20KEY-----%0A"
            "MIIEowIBAAKCAQEAsecretEncodedBody%0A"
            "-----END%20RSA%20PRIVATE%20KEY-----"
        ),
    ],
)
def test_final_prompt_dto_fails_closed_on_common_confidential_credentials(
    suspect: str,
) -> None:
    item = (
        command()
        .deterministic.evidence_items[-1]
        .model_copy(update={"claim": suspect, "excerpt": suspect})
    )

    with pytest.raises(ValueError, match="model data boundary"):
        _evidence_payload((item,), scopes={AuthorityScope.QUALIFICATION_STATE})


@pytest.mark.parametrize(
    "ordinary",
    [
        "The supplier treats the first criterion as absolute.",
        "The secret supplier strategy remains outside this demo.",
        "Password policy training is scheduled for next month.",
        "Token inventory is an ordinary procurement planning term here.",
        "The API key rotation policy has no credential values in this evidence.",
    ],
)
def test_final_prompt_dto_does_not_overblock_ordinary_business_words(
    ordinary: str,
) -> None:
    item = (
        command()
        .deterministic.evidence_items[-1]
        .model_copy(update={"claim": ordinary, "excerpt": ordinary})
    )

    payload = _evidence_payload((item,), scopes={AuthorityScope.QUALIFICATION_STATE})

    assert payload["evidence"][0]["claim"] == ordinary


def test_recursive_scrubber_redacts_strings_in_keys_and_nested_collections() -> None:
    secrets = (
        "api_key=nested-dictionary-key-secret",
        "password=nested-list-secret",
        "token=nested-tuple-secret",
        "-----BEGIN PRIVATE KEY-----\nprivate-body\n-----END PRIVATE KEY-----",
    )
    value = {
        secrets[0]: [secrets[1], (secrets[2],), {secrets[3]}],
        "ordinary": "The secret supplier strategy is ordinary business prose.",
    }

    scrubbed = _scrub(value)

    serialized = repr(scrubbed)
    assert all(secret not in serialized for secret in secrets)
    assert scrubbed["ordinary"] == value["ordinary"]


def test_final_prompt_dto_rejects_non_allowlisted_evidence_identifiers() -> None:
    item = (
        command()
        .deterministic.evidence_items[-1]
        .model_copy(update={"evidence_id": "not an identifier"})
    )
    with pytest.raises(ValueError, match="model data boundary"):
        _evidence_payload((item,), scopes={AuthorityScope.QUALIFICATION_STATE})


def _contaminate_decision_analysis(field: str, suspect: str):
    analysis = analyze_case(command().deterministic)
    ranking = analysis.ranking
    stage = ranking.stages[0]
    if field == "analysis_id":
        return analysis.model_copy(update={"analysis_id": suspect})
    if field == "recommended_option_id":
        return analysis.model_copy(
            update={
                "ranking": ranking.model_copy(update={"recommended_option_id": suspect})
            }
        )
    if field == "policy_version":
        return analysis.model_copy(
            update={"ranking": ranking.model_copy(update={"policy_version": suspect})}
        )
    if field == "comparator":
        changed = stage.model_copy(update={"comparator": suspect})
    elif field == "value_option_id":
        changed_value = stage.values[0].model_copy(update={"option_id": suspect})
        changed = stage.model_copy(
            update={"values": (changed_value, *stage.values[1:])}
        )
    elif field == "value":
        changed_value = stage.values[0].model_copy(update={"value": suspect})
        changed = stage.model_copy(
            update={"values": (changed_value, *stage.values[1:])}
        )
    elif field == "retained_option_id":
        changed = stage.model_copy(update={"retained_option_ids": (suspect,)})
    else:  # pragma: no cover - protects the test helper itself
        raise AssertionError(field)
    return analysis.model_copy(
        update={
            "ranking": ranking.model_copy(
                update={"stages": (changed, *ranking.stages[1:])}
            )
        }
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "suspect"),
    [
        (
            "analysis_id",
            "Bearer eyJhbGciOiJSUzI1NiJ9.eyJvaWQiOiIxMjM0NTY3OCJ9.abcdefghijklmnopqrstuvwxyz012345",
        ),
        ("recommended_option_id", "upn: alex@example.invalid"),
        ("policy_version", "client_secret=fictional-confidential-value"),
        ("comparator", "tenant_id=11111111-2222-3333-4444-555555555555"),
        ("value_option_id", "oid is 11111111-2222-3333-4444-555555555555"),
        (
            "value",
            "OBO assertion=eyJhbGciOiJSUzI1NiJ9.eyJ0aWQiOiIxMjM0NTY3OCJ9.abcdefghijklmnopqrstuvwxyz012345",
        ),
        ("retained_option_id", "https://user:password@example.invalid/project"),
    ],
)
async def test_every_decision_dto_field_fails_closed_before_agent_invocation(
    field: str, suspect: str
) -> None:
    contaminated = _contaminate_decision_analysis(field, suspect)
    factory, made = agents()

    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(factory, lambda _: contaminated).analyze(command())

    assert cast(FakeAgent, made[0].decision).payloads == []
    public = caught.value
    exposed = " ".join(
        (
            str(public),
            repr(public),
            repr(public.args),
            public.partial_result.model_dump_json(),
        )
    )
    assert suspect not in exposed


@pytest.mark.anyio
async def test_public_unavailable_exception_detaches_original_exception_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "Bearer eyJhbGciOiJSUzI1NiJ9.secret-bearing-payload.signature-value"

    class FailedWorkflow:
        async def run(self, value):
            raise RuntimeError(secret)

    monkeypatch.setattr(
        "agents.orchestrator.workflow.build_framework_workflow",
        lambda *args, **kwargs: FailedWorkflow(),
    )
    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(agents()[0], analyze_case).analyze(command())

    public = caught.value
    assert public.__context__ is None
    assert public.__cause__ is None
    assert secret not in repr(public)
    assert secret not in repr(public.args)
    assert secret not in repr(vars(public))
    assert secret not in "".join(traceback.format_exception(public))
    assert secret not in public.partial_result.model_dump_json()


@pytest.mark.anyio
async def test_public_boundary_rebuilds_nested_unavailable_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = analyze_case(command().deterministic)
    nested = AgentExplanationUnavailable(
        PartialDeterministicResult(
            analysis_version=analysis,
            evidence_items=analysis.evidence_items,
        )
    )
    secret = "client_secret=nested-public-exception-secret"
    nested.__context__ = RuntimeError(secret)

    class FailedWorkflow:
        async def run(self, value):
            raise nested

    monkeypatch.setattr(
        "agents.orchestrator.workflow.build_framework_workflow",
        lambda *args, **kwargs: FailedWorkflow(),
    )
    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(agents()[0], analyze_case).analyze(command())

    assert caught.value is not nested
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert secret not in repr(vars(caught.value))
    assert secret not in "".join(traceback.format_exception(caught.value))


def _walk_public_traceback_objects(error: BaseException) -> list[object]:
    """Collect inspectable public traceback state without following code globals."""
    roots: list[object] = []
    current = error.__traceback__
    while current is not None:
        module_name = current.tb_frame.f_globals.get("__name__", "")
        if module_name.startswith("agents.orchestrator"):
            roots.append(current.tb_frame.f_locals)
        current = current.tb_next
    seen: set[int] = set()
    found: list[object] = []
    pending = [(item, 0) for item in roots]
    while pending:
        value, depth = pending.pop()
        identity = id(value)
        if identity in seen or depth > 8:
            continue
        seen.add(identity)
        found.append(value)
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, (list, tuple, set, frozenset)):
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, BaseException):
            pending.extend((item, depth + 1) for item in value.args)
            pending.extend((item, depth + 1) for item in vars(value).values())
        elif not isinstance(
            value,
            (
                str,
                bytes,
                int,
                float,
                bool,
                type(None),
                types.ModuleType,
                types.FunctionType,
                types.MethodType,
                type,
            ),
        ):
            try:
                pending.extend((item, depth + 1) for item in vars(value).values())
            except TypeError:
                pass
    return found


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["build", "run", "outputs"])
async def test_public_traceback_has_no_path_to_raw_command_or_sdk_failure(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    secret = f"api_key=task16-{failure}-confidential-value-1234567890"
    original = command()
    evidence = list(original.deterministic.evidence_items)
    evidence[-1] = evidence[-1].model_copy(update={"claim": secret, "excerpt": secret})
    contaminated = original.model_copy(
        update={
            "deterministic": original.deterministic.model_copy(
                update={"evidence_items": tuple(evidence)}
            )
        }
    )
    raw_error = RuntimeError(f"SDK retained raw failure: {secret}")

    class FailedRun:
        def __init__(self) -> None:
            self.raw_error = raw_error

        def get_outputs(self):
            raise self.raw_error

    class FailedWorkflow:
        def __init__(self) -> None:
            self.raw_error = raw_error

        async def run(self, value):
            if failure == "run":
                raise self.raw_error
            return FailedRun()

    def build(*args, **kwargs):
        if failure == "build":
            raise raw_error
        return FailedWorkflow()

    monkeypatch.setattr("agents.orchestrator.workflow.build_framework_workflow", build)

    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(agents()[0], analyze_case).analyze(contaminated)

    public = caught.value
    reachable = _walk_public_traceback_objects(public)
    assert raw_error not in reachable
    assert all(secret not in repr(value) for value in reachable)
    assert secret not in public.partial_result.model_dump_json()
    assert secret not in repr(public)
    assert public.__cause__ is None
    assert public.__context__ is None


@pytest.mark.anyio
async def test_fresh_workflow_and_executors_are_built_for_every_run() -> None:
    factory, made = agents()
    observed: list[tuple[str, ...]] = []
    orchestrator = Orchestrator(
        factory, analyze_case, topology_observer=observed.append
    )

    await orchestrator.analyze(command())
    await orchestrator.analyze(command())

    assert len(made) == 2
    assert made[0] is not made[1]
    assert made[0].signal is not made[1].signal
    assert not hasattr(orchestrator, "framework_workflows")
    assert not hasattr(orchestrator, "topologies")
    assert observed == [
        ("signal", "context", "deterministic_analysis", "decision"),
        ("signal", "context", "deterministic_analysis", "decision"),
    ]


@pytest.mark.anyio
async def test_completed_workflow_does_not_retain_case_agents() -> None:
    references: list[weakref.ReferenceType[FakeAgent]] = []

    def factory() -> LocalAgentSet:
        result = agents()[0]()
        references.extend(
            weakref.ref(cast(FakeAgent, item))
            for item in (result.signal, result.context, result.decision)
        )
        return result

    orchestrator = Orchestrator(factory, analyze_case)
    await orchestrator.analyze(command())
    await asyncio.sleep(0)
    gc.collect()
    assert all(reference() is None for reference in references)


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["build", "run", "outputs", "multiple"])
async def test_framework_failures_preserve_one_redacted_deterministic_result(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    calls = 0

    def counting_analyze(value: AnalyzeCaseCommand):
        nonlocal calls
        calls += 1
        return analyze_case(value)

    class FailedRun:
        def get_outputs(self):
            if failure == "outputs":
                raise RuntimeError("Bearer eyJhbGciOiJSUzI1NiJ9.secret.signature")
            return [object(), object()]

    class FailedWorkflow:
        def __init__(self, analyze) -> None:
            self._analyze = analyze

        async def run(self, value):
            if failure == "run":
                raise RuntimeError("client_secret=do-not-leak")
            self._analyze(value.deterministic)
            return FailedRun()

    def build(*args, **kwargs):
        if failure == "build":
            raise RuntimeError("OBO assertion=do-not-leak")
        return FailedWorkflow(args[1])

    monkeypatch.setattr("agents.orchestrator.workflow.build_framework_workflow", build)
    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(agents()[0], counting_analyze).analyze(command())
    assert calls == 1
    assert (
        str(caught.value)
        == "Agent explanation unavailable; deterministic result preserved."
    )
    assert "secret" not in caught.value.partial_result.model_dump_json().lower()


@pytest.mark.anyio
async def test_local_fallback_has_same_contract_and_no_network_agent() -> None:
    result = await Orchestrator(LocalAgentSet.deterministic, analyze_case).analyze(
        command()
    )

    assert result.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.explanation_status == "available"
    assert result.decision_explanation is not None
    assert result.decision_explanation.recommended_option_id == "RL-OPTION-COMBINED"
