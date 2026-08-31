from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final
from urllib.parse import urlsplit

from data.domain.common import RuntimeMode
from data.domain.evidence import (
    AuthorityScope,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    RetrievalHealth,
    UncertaintyState,
)

from .errors import WorkIQProtocolError, WorkIQResponseLimitError

_MAX_FACTS: Final = 128
_MAX_TEXT_CHARS: Final = 32_768
_ALLOWED_EXACT_HOSTS: Final = frozenset(
    {
        "teams.microsoft.com",
        "outlook.office.com",
        "outlook.office365.com",
    }
)
_ALLOWED_SCOPES: Final = {
    "supplier_statement": AuthorityScope.SUPPLIER_STATEMENT,
    "collaboration_statement": AuthorityScope.COLLABORATION_STATEMENT,
}


def _bounded_string(value: Any, label: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if isinstance(value, str) and len(value) > _MAX_TEXT_CHARS:
        raise WorkIQResponseLimitError(f"Work IQ {label} exceeds size limit")
    if not isinstance(value, str) or not value.strip():
        raise WorkIQProtocolError(f"Work IQ {label} is malformed")
    return value.strip()


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _trusted_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = host in _ALLOWED_EXACT_HOSTS or (
        host.endswith(".sharepoint.com") and host != "sharepoint.com"
    )
    if (
        parsed.scheme != "https"
        or not allowed
        or not parsed.path
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return None
    return value


def _citation(fact: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = fact.get("citation")
    if isinstance(direct, Mapping):
        return direct
    citations = fact.get("citations")
    if isinstance(citations, list) and len(citations) == 1:
        candidate = citations[0]
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _fact_item(
    fact: Mapping[str, Any],
    *,
    artifact_id: str,
    index: int,
    case_id: str,
    analysis_id: str,
    retrieved_at: datetime,
) -> EvidenceItem:
    claim = _bounded_string(fact.get("claim"), "fact claim")
    assert claim is not None
    fact_id = _bounded_string(fact.get("factId"), "fact ID", required=False)
    citation = _citation(fact)
    citation_url = _trusted_url(citation.get("url")) if citation else None
    source_id = (
        _bounded_string(citation.get("sourceId"), "citation source ID", required=False)
        if citation
        else None
    )
    excerpt = (
        _bounded_string(citation.get("excerpt"), "citation excerpt", required=False)
        if citation
        else None
    )
    source_kind = citation.get("sourceType") if citation else None
    source_timestamp = _timestamp(fact.get("sourceTimestamp"))
    raw_scope = fact.get("authorityScope")
    scope = _ALLOWED_SCOPES.get(raw_scope) if isinstance(raw_scope, str) else None
    trusted = bool(
        citation_url
        and source_id
        and excerpt
        and source_timestamp
        and scope
        and source_kind in {"microsoft365", "tenant"}
    )
    return EvidenceItem(
        evidence_id=fact_id or f"{artifact_id}:fact:{index}",
        case_id=case_id,
        kind=(
            EvidenceKind.SOURCE_STATEMENT
            if trusted
            else EvidenceKind.CONTEXTUAL_EVIDENCE
        ),
        authority_scope=(scope,) if trusted and scope is not None else (),
        source_system=EvidenceSourceSystem.WORK_IQ,
        source_id=source_id or artifact_id,
        source_timestamp=source_timestamp,
        retrieved_at=retrieved_at,
        retrieved_for_analysis_id=analysis_id,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=_timestamp(fact.get("effectiveAt")),
        expires_at=_timestamp(fact.get("expiresAt")),
        claim=claim,
        excerpt=excerpt if trusted else None,
        citation_url=citation_url if trusted else None,
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
        requirement=(
            EvidenceRequirement.REQUIRED_AUTHORITATIVE
            if trusted
            else EvidenceRequirement.CONTEXTUAL
        ),
        uncertainty_state=UncertaintyState.CERTAIN,
    )


def _contextual_text_item(
    text: str,
    *,
    artifact_id: str,
    part_index: int,
    case_id: str,
    analysis_id: str,
    retrieved_at: datetime,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"{artifact_id}:text:{part_index}",
        case_id=case_id,
        kind=EvidenceKind.CONTEXTUAL_EVIDENCE,
        authority_scope=(),
        source_system=EvidenceSourceSystem.WORK_IQ,
        source_id=artifact_id,
        source_timestamp=None,
        retrieved_at=retrieved_at,
        retrieved_for_analysis_id=analysis_id,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=None,
        expires_at=None,
        claim=text,
        excerpt=None,
        citation_url=None,
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
        requirement=EvidenceRequirement.CONTEXTUAL,
        uncertainty_state=UncertaintyState.UNCERTAIN,
    )


def normalize_a2a_evidence(
    payload: Mapping[str, Any],
    *,
    case_id: str,
    analysis_id: str,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise WorkIQProtocolError("Work IQ result is missing")
    status = result.get("status")
    if not isinstance(status, Mapping) or status.get("state") != "TASK_STATE_COMPLETED":
        raise WorkIQProtocolError("Work IQ task did not complete")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > 64:
        raise WorkIQResponseLimitError("Work IQ artifact count is invalid")
    items: list[EvidenceItem] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise WorkIQProtocolError("Work IQ artifact is malformed")
        artifact_id = _bounded_string(artifact.get("artifactId"), "artifact ID")
        assert artifact_id is not None
        parts = artifact.get("parts")
        if not isinstance(parts, list) or len(parts) > 32:
            raise WorkIQResponseLimitError("Work IQ artifact part count is invalid")
        for part_index, part in enumerate(parts):
            if not isinstance(part, Mapping):
                raise WorkIQProtocolError("Work IQ artifact part is malformed")
            text = part.get("text")
            if text is not None:
                bounded_text = _bounded_string(text, "artifact text")
                assert bounded_text is not None
                items.append(
                    _contextual_text_item(
                        bounded_text,
                        artifact_id=artifact_id,
                        part_index=part_index,
                        case_id=case_id,
                        analysis_id=analysis_id,
                        retrieved_at=retrieved_at,
                    )
                )
            data = part.get("data")
            if data is None:
                continue
            if not isinstance(data, Mapping):
                raise WorkIQProtocolError("Work IQ artifact data is malformed")
            facts = data.get("facts")
            if not isinstance(facts, list):
                raise WorkIQProtocolError("Work IQ facts are malformed")
            if len(items) + len(facts) > _MAX_FACTS:
                raise WorkIQResponseLimitError("Work IQ fact count exceeds limit")
            for index, fact in enumerate(facts):
                if not isinstance(fact, Mapping):
                    raise WorkIQProtocolError("Work IQ fact is malformed")
                items.append(
                    _fact_item(
                        fact,
                        artifact_id=artifact_id,
                        index=index,
                        case_id=case_id,
                        analysis_id=analysis_id,
                        retrieved_at=retrieved_at,
                    )
                )
    return tuple(items)
