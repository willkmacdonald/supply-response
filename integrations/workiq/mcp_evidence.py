"""One bounded discovery/fetch/validation lifetime per delegated source retrieval."""

import asyncio
from datetime import datetime
from typing import Final, Literal

from apps.api.app.auth import AuthenticatedActor

from .async_obo import AsyncWorkIQOboExchange
from .discovery import discover_locations, question_for
from .errors import WorkIQError
from .mcp import WorkIQMcpClient
from .message_evidence import evidence_from_message
from .models import (
    DiscoveryTopic,
    SourceBinding,
    SourceKind,
    WorkIQRetrieval,
    WorkIQRetrievalLineage,
)

SOURCE_TIMEOUT_SECONDS: Final = 120
FailureStage = Literal["discovery", "fetch", "validation", "authentication", "timeout"]


class WorkIQSourceError(WorkIQError):
    def __init__(self, source_kind: SourceKind, stage: FailureStage) -> None:
        self.source_kind: SourceKind = source_kind
        self.stage: FailureStage = stage
        super().__init__(f"Work IQ {source_kind} source unavailable ({stage})")


class WorkIQMcpEvidencePort:
    def __init__(
        self,
        *,
        client: WorkIQMcpClient,
        obo: AsyncWorkIQOboExchange,
        binding: SourceBinding,
    ) -> None:
        self._client = client
        self._obo = obo
        self._binding = binding

    async def retrieve_supplier_signal(
        self,
        *,
        actor: AuthenticatedActor,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> WorkIQRetrieval:
        return await self._retrieve(
            source_kind="supplier",
            actor=actor,
            source_id=source_id,
            case_id=case_id,
            analysis_id=analysis_id,
            retrieved_at=retrieved_at,
        )

    async def retrieve_quality_context(
        self,
        *,
        actor: AuthenticatedActor,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> WorkIQRetrieval:
        return await self._retrieve(
            source_kind="quality",
            actor=actor,
            source_id=source_id,
            case_id=case_id,
            analysis_id=analysis_id,
            retrieved_at=retrieved_at,
        )

    async def _retrieve(
        self,
        *,
        source_kind: SourceKind,
        actor: AuthenticatedActor,
        source_id: str,
        case_id: str,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> WorkIQRetrieval:
        binding = self._binding
        if (
            not isinstance(actor, AuthenticatedActor)
            or actor.tenant_id != binding.tenant_id
            or actor.object_id != binding.alex_object_id
        ):
            raise WorkIQSourceError(source_kind, "authentication")
        expected_id = (
            binding.supplier_source_id
            if source_kind == "supplier"
            else binding.quality_source_id
        )
        if source_id != expected_id:
            raise WorkIQSourceError(source_kind, "validation")
        stage: FailureStage = "authentication"
        token = None
        session = None
        answer = None
        payload = None
        try:
            async with asyncio.timeout(SOURCE_TIMEOUT_SECONDS):
                token = await self._obo.exchange(actor)
                stage = "discovery"
                async with self._client.session(access_token=token.reveal()) as session:
                    token = None
                    answer = await session.ask(
                        question_for(DiscoveryTopic(source_kind))
                    )
                    locations = discover_locations(answer, source_kind=source_kind)
                    conversation_id = answer["conversationId"]
                    answer = None
                    # Scope checks happen independently of configured source IDs.
                    scoped = tuple(loc for loc in locations if loc.within(binding))
                    candidates = tuple(
                        loc for loc in scoped if loc.message_id == expected_id
                    )
                    if not candidates:
                        raise WorkIQSourceError(source_kind, "discovery")
                    evidence = []
                    for location in candidates:
                        stage = "fetch"
                        payload = await session.fetch(location.fetch_path)
                        stage = "validation"
                        evidence.append(
                            evidence_from_message(
                                payload["results"][0]["data"],
                                location=location,
                                binding=binding,
                                case_id=case_id,
                                analysis_id=analysis_id,
                                retrieved_at=retrieved_at,
                            )
                        )
                        payload = None
                    if len(evidence) != 1:
                        raise WorkIQSourceError(source_kind, "validation")
                    return WorkIQRetrieval(
                        evidence=tuple(evidence),
                        lineage=WorkIQRetrievalLineage(
                            context_id=conversation_id,
                            task_id="",
                            artifact_ids=(),
                            source_ids=(evidence[0].source_id,),
                            protocol="mcp",
                            request_ids=session.request_ids,
                        ),
                    )
        except TimeoutError:
            stage = "timeout"
        except Exception:  # noqa: BLE001, S110 - sanitized outside handler, never log payloads
            pass
        finally:
            token = None
            session = None
            answer = None
            payload = None
        # Do not chain discarded raw payloads or credential-bearing failures.
        raise WorkIQSourceError(source_kind, stage)
