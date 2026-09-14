"""One bounded discovery/fetch/validation lifetime per delegated source retrieval."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Final, Literal

from apps.api.app.auth import AuthenticatedActor
from data.domain.inbound import InboundEmailError, SupplierEmailSource

from .async_obo import AsyncWorkIQOboExchange
from .errors import WorkIQError, WorkIQProtocolError, WorkIQResponseLimitError
from .inbox import InboxCheck, discover_inbox, review_email
from .mcp import WorkIQMcpClient
from .message_evidence import evidence_from_message
from .models import (
    SourceBinding,
    SourceKind,
    WorkIQRetrieval,
    WorkIQRetrievalLineage,
)
from .structured_discovery import StructuredDiscoveryError, discover_structured

SOURCE_TIMEOUT_SECONDS: Final = 120
INBOX_TIMEOUT_SECONDS: Final = 119
FailureStage = Literal["discovery", "fetch", "validation", "authentication", "timeout"]
_logger = logging.getLogger(__name__)


def _safe_failure_reason(error: Exception) -> tuple[str, int]:
    """Map local protocol errors to constants; never format an exception for logs."""
    if type(error) is WorkIQResponseLimitError:
        return "response_limit", 0
    if type(error) is not WorkIQProtocolError or len(error.args) != 1:
        return "unknown", 0
    message = error.args[0]
    if type(message) is not str:
        return "unknown", 0
    status = re.fullmatch(r"Work IQ HTTP ([1-5][0-9]{2})", message)
    if status is not None:
        return "http_error", int(status[1])
    reasons = {
        "Work IQ initialization is invalid": "initialization_shape",
        "Work IQ RPC response is invalid": "rpc_shape",
        "Work IQ tool failed": "tool_error",
        "Work IQ tool response is invalid": "tool_shape",
        "Work IQ discovery response is invalid": "discovery_shape",
        "Work IQ response contains malformed JSON": "json_invalid",
        "Work IQ response has unsupported content type": "content_type",
        "Work IQ request unavailable": "request_unavailable",
        "Work IQ session header is invalid": "session_header",
        "Work IQ session header changed": "session_header",
        "Work IQ protocol header is invalid": "protocol_header",
        "Work IQ notification response is not empty": "notification_body",
        "Work IQ entity retrieval failed": "entity_response",
    }
    return reasons.get(message, "unknown"), 0


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

    async def _review_inbound(
        self,
        *,
        actor: AuthenticatedActor,
        internet_message_id: str,
        review_fingerprint: str,
        checked_at: datetime,
        case_id: str = "inbox-review",
        analysis_id: str = "inbox-review",
    ) -> tuple[SupplierEmailSource, WorkIQRetrieval]:
        binding = self._binding
        if (
            not isinstance(actor, AuthenticatedActor)
            or actor.tenant_id != binding.tenant_id
            or actor.object_id != binding.alex_object_id
        ):
            raise InboundEmailError("INBOUND_EMAIL_UNAVAILABLE")
        token = None
        session = None
        try:
            async with asyncio.timeout(INBOX_TIMEOUT_SECONDS):
                token = await self._obo.exchange(actor)
                async with self._client.session(access_token=token.reveal()) as session:
                    token = None
                    source, evidence = await review_email(
                        session,
                        binding=binding,
                        internet_message_id=internet_message_id,
                        review_fingerprint=review_fingerprint,
                        checked_at=checked_at,
                        case_id=case_id,
                        analysis_id=analysis_id,
                    )
                    return source, WorkIQRetrieval(
                        evidence=(evidence,),
                        lineage=WorkIQRetrievalLineage(
                            context_id="",
                            task_id="",
                            artifact_ids=(),
                            source_ids=(evidence.source_id,),
                            protocol="mcp",
                            request_ids=session.request_ids,
                        ),
                    )
        except InboundEmailError:
            raise
        except Exception:  # noqa: BLE001 - discard provider details
            _logger.warning("workiq_inbound_diagnostic reason=unavailable")
        finally:
            token = session = None
        raise InboundEmailError("INBOUND_EMAIL_UNAVAILABLE") from None

    async def review_inbound_email(
        self,
        *,
        actor: AuthenticatedActor,
        internet_message_id: str,
        review_fingerprint: str,
        checked_at: datetime,
    ) -> SupplierEmailSource:
        source, _ = await self._review_inbound(
            actor=actor,
            internet_message_id=internet_message_id,
            review_fingerprint=review_fingerprint,
            checked_at=checked_at,
        )
        return source

    async def retrieve_bound_supplier_signal(
        self,
        *,
        actor: AuthenticatedActor,
        source: SupplierEmailSource,
        case_id: str,
        analysis_id: str,
        retrieved_at: datetime,
    ) -> WorkIQRetrieval:
        if (
            source.tenant_id != self._binding.tenant_id
            or source.mailbox_object_id != self._binding.alex_object_id
        ):
            raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
        current, retrieval = await self._review_inbound(
            actor=actor,
            internet_message_id=source.internet_message_id,
            review_fingerprint=source.review_fingerprint,
            checked_at=retrieved_at,
            case_id=case_id,
            analysis_id=analysis_id,
        )
        if current.facts != source.facts:
            raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
        return retrieval

    async def check_inbox(
        self, *, actor: AuthenticatedActor, checked_at: datetime
    ) -> InboxCheck:
        """Run one delegated, bounded inbox check for the configured Alex actor."""
        binding = self._binding
        if (
            not isinstance(actor, AuthenticatedActor)
            or actor.tenant_id != binding.tenant_id
            or actor.object_id != binding.alex_object_id
        ):
            raise WorkIQSourceError("supplier", "authentication")
        token = None
        session = None
        stage: FailureStage = "authentication"
        failed = False
        try:
            async with asyncio.timeout(INBOX_TIMEOUT_SECONDS):
                token = await self._obo.exchange(actor)
                stage = "discovery"
                async with self._client.session(access_token=token.reveal()) as session:
                    token = None
                    return await discover_inbox(
                        session, binding=binding, checked_at=checked_at
                    )
        except TimeoutError:
            stage = "timeout"
            failed = True
        except Exception:  # noqa: BLE001 - discard and sanitize upstream failures
            failed = True
        finally:
            token = None
            session = None
        if failed:
            _logger.warning(
                "workiq_inbox_diagnostic stage=%s reason=unavailable", stage
            )
        raise WorkIQSourceError("supplier", stage) from None

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
        step = "authentication"
        reason, http_status = "unknown", 0
        parsed_count = scoped_count = matched_count = -1
        token = None
        session = None
        payload = None
        try:
            async with asyncio.timeout(SOURCE_TIMEOUT_SECONDS):
                token = await self._obo.exchange(actor)
                stage = "discovery"
                step = "initialize"
                async with self._client.session(access_token=token.reveal()) as session:
                    token = None
                    step = "structured_discovery"
                    locations = await discover_structured(
                        session, source_kind=source_kind, binding=binding
                    )
                    parsed_count = min(len(locations), 5)
                    if not locations:
                        reason = "no_locations"
                        raise WorkIQSourceError(source_kind, "discovery")
                    if locations[0].message_id != expected_id:
                        reason = "message_mismatch"
                        raise WorkIQSourceError(source_kind, "discovery")
                    candidates = locations
                    scoped_count = matched_count = len(candidates)
                    matched_count = min(len(candidates), 5)
                    evidence = []
                    for location in candidates:
                        stage = "fetch"
                        step = "fetch"
                        payload = await session.fetch(location.fetch_path)
                        stage = "validation"
                        step = "validate_entity"
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
                            context_id="",
                            task_id="",
                            artifact_ids=(),
                            source_ids=(evidence[0].source_id,),
                            protocol="mcp",
                            request_ids=session.request_ids,
                        ),
                    )
        except TimeoutError:
            stage = "timeout"
            reason = "timeout"
        except StructuredDiscoveryError as error:
            stage = "discovery"
            reason = error.reason
        except Exception as error:  # noqa: BLE001 - allowlisted diagnostics only
            if reason == "unknown":
                reason, http_status = _safe_failure_reason(error)
        finally:
            token = None
            session = None
            payload = None
        # Do not chain discarded raw payloads or credential-bearing failures.
        _logger.warning(
            "workiq_source_diagnostic source=%s stage=%s step=%s reason=%s "
            "http_status=%d parsed=%d scoped=%d matched=%d",
            source_kind,
            stage,
            step,
            reason,
            http_status,
            parsed_count,
            scoped_count,
            matched_count,
        )
        raise WorkIQSourceError(source_kind, stage)
