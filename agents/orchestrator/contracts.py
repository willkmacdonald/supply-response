from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data.domain.analysis import AnalysisVersion
from data.domain.evidence import AuthorityScope, EvidenceItem
from services.analysis.service import AnalyzeCaseCommand


class AgentContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetrievalLineage(AgentContract):
    context_id: str = Field(max_length=256)
    task_id: str = Field(max_length=256)
    artifact_ids: tuple[str, ...] = Field(max_length=64)
    source_ids: tuple[str, ...] = Field(max_length=64)
    protocol: Literal["a2a", "mcp"] = "a2a"
    request_ids: tuple[str, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def validate_protocol_lineage(self) -> RetrievalLineage:
        if self.protocol == "a2a" and not self.context_id:
            raise ValueError("A2A retrieval lineage requires context")
        if self.protocol == "a2a" and not self.task_id:
            raise ValueError("A2A retrieval lineage requires a task ID")
        if self.protocol == "mcp" and (self.task_id or self.artifact_ids):
            raise ValueError("MCP retrieval lineage cannot contain A2A identifiers")
        return self


class AnalyzeCommand(AgentContract):
    """Server-created command; no actor assertion or tenant binding is permitted."""

    deterministic: AnalyzeCaseCommand
    retrieval_lineage: tuple[RetrievalLineage, ...] = Field(default=(), max_length=8)


class BoundedEvidence(AgentContract):
    evidence_id: str = Field(min_length=1, max_length=128)
    authority_scope: tuple[str, ...] = Field(max_length=8)
    claim: str = Field(min_length=1, max_length=2_000)
    excerpt: str = Field(min_length=1, max_length=2_000)


class ExtractedReference(AgentContract):
    evidence_id: str = Field(min_length=1, max_length=128)
    authority_scope: AuthorityScope
    source_span: str = Field(min_length=1, max_length=2_000)


class ExtractedFacts(AgentContract):
    facts: tuple[ExtractedReference, ...] = Field(default=(), max_length=20)
    uncertainties: tuple[ExtractedReference, ...] = Field(default=(), max_length=20)


class DecisionExplanation(AgentContract):
    recommended_option_id: str = Field(min_length=1, max_length=128)
    stage_references: tuple[str, ...] = Field(max_length=20)
    explanation: str = Field(min_length=1, max_length=2_000)


class DecisionSelection(AgentContract):
    recommended_option_id: str = Field(min_length=1, max_length=128)
    stage_references: tuple[str, ...] = Field(max_length=20)


class PartialDeterministicResult(AgentContract):
    analysis_version: AnalysisVersion
    evidence_items: tuple[EvidenceItem, ...]


class OrchestrationResult(AgentContract):
    analysis_version: AnalysisVersion
    signal_extraction: ExtractedFacts | None = None
    context_extraction: ExtractedFacts | None = None
    decision_explanation: DecisionExplanation | None = None
    explanation_status: Literal["available", "rejected", "unavailable"]


class AgentExplanationUnavailable(RuntimeError):
    """Explanation failed without weakening or discarding deterministic analysis."""

    def __init__(self, partial_result: PartialDeterministicResult) -> None:
        super().__init__(
            "Agent explanation unavailable; deterministic result preserved."
        )
        self.partial_result = partial_result


class SignalMessage(AgentContract):
    command: AnalyzeCommand
    extraction: ExtractedFacts | None = None
    failed: bool = False


class ContextMessage(AgentContract):
    command: AnalyzeCommand
    signal: ExtractedFacts | None = None
    context: ExtractedFacts | None = None
    failed: bool = False


class DeterministicMessage(AgentContract):
    analysis_version: AnalysisVersion
    signal: ExtractedFacts | None = None
    context: ExtractedFacts | None = None
    failed: bool = False
