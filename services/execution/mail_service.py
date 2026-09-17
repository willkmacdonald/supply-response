from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from data.domain.decisions import Decision, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.execution import ExecutionAction, ExecutionActionKind
from data.domain.outbound_mail import (
    ReviewedSupplierEmail,
    SupplierEmailDelivery,
    SupplierEmailRevision,
)
from integrations.graph_mail.client import (
    GraphMailError,
    GraphMailPort,
    GraphMailSubmissionUncertain,
    ProviderMessage,
)
from services.execution.currentness import (
    ExecutionProposalStale,
    guard_execution_current,
)
from services.execution.worker import UnitOfWorkFactory
from services.persistence.store import PersistenceError, RecordNotFound


class EmailAuthorizationError(PermissionError):
    """The actor is not the configured Alex identity."""


class EmailRevisionConflict(RuntimeError):
    """The requested content revision is no longer current."""


class EmailStateError(RuntimeError):
    """The current Decision cannot produce a reviewed supplier email."""


class EmailSendDisabled(EmailStateError):
    """Real supplier email sending is not enabled."""


def deterministic_email_id(decision_id: str) -> str:
    return f"RL-EMAIL-{uuid5(NAMESPACE_URL, f'{decision_id}:supplier-email')}"


class ReviewedEmailService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        from_address: str,
        to_address: str,
        configured_actor: IdentitySnapshot,
        graph_mail: GraphMailPort | None = None,
        mail_send_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._from_address = from_address
        self._to_address = to_address
        self._configured_actor = configured_actor
        self._graph_mail = graph_mail
        self._mail_send_enabled = mail_send_enabled
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _identity(actor: object) -> IdentitySnapshot:
        converter = getattr(actor, "to_identity_snapshot", None)
        return converter() if callable(converter) else actor  # type: ignore[return-value]

    def _require_actor(self, actor: IdentitySnapshot) -> None:
        actor = self._identity(actor)
        expected = self._configured_actor
        fixed_fields_match = (
            actor.persona_id == expected.persona_id == "RL-PERSONA-ALEX"
            and actor.source_id == expected.source_id == "RL-ENTRA-ALEX"
            and actor.identity_source
            is expected.identity_source
            is IdentitySource.ENTRA
            and actor.effective_roles
            == expected.effective_roles
            == ("material_planner", "response_approver")
        )
        configured_ids_match = (
            expected.tenant_id is None or actor.tenant_id == expected.tenant_id
        ) and (expected.object_id is None or actor.object_id == expected.object_id)
        if not fixed_fields_match or not configured_ids_match:
            raise EmailAuthorizationError("Only the configured Alex can review email")

    @staticmethod
    def _require_current_projection(uow, decision: Decision) -> None:
        projection = uow.cases.get_projection(decision.case_id)
        if (
            projection.current_decision_id != decision.decision_id
            or projection.current_analysis_id != decision.analysis_id
            or projection.current_analysis_hash != decision.analysis_material_hash
        ):
            raise ExecutionProposalStale("Execution Decision is no longer current")

    @staticmethod
    def _draft_action(uow, decision_id: str) -> ExecutionAction:
        actions = tuple(
            action
            for action in uow.execution.list_actions(decision_id=decision_id)
            if action.kind is ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT
        )
        if len(actions) != 1 or actions[0].draft_artifact_id is None:
            raise EmailStateError(
                "The supplier email is not available until action planning completes."
            )
        action = actions[0]
        try:
            artifact = uow.execution.get_draft_artifact(action.action_id)
        except (RecordNotFound, PersistenceError) as error:
            raise EmailStateError(
                "The supplier email does not match its planned action."
            ) from error
        if (
            action.decision_id != decision_id
            or artifact.action_id != action.action_id
            or artifact.decision_id != decision_id
            or artifact.artifact_id != action.draft_artifact_id
        ):
            raise EmailStateError(
                "The supplier email does not match its planned action."
            )
        return action

    @staticmethod
    def _initial_content(
        decision: Decision, actions: tuple[ExecutionAction, ...]
    ) -> tuple[str, str]:
        option = decision.selected_option
        if option is None or decision.selected_option_id != option.option_id:
            raise EmailStateError(
                "The supplier email requires a current approved response."
            )
        coordination = tuple(
            action.purpose
            for action in actions
            if action.kind
            not in (
                ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT,
                ExecutionActionKind.UPDATE_DISRUPTION_STATUS,
            )
            and action.purpose is not None
        )
        if not coordination:
            raise EmailStateError(
                "The supplier email requires a planned approved response."
            )
        coordination_text = "\n".join(f"- {purpose}" for purpose in coordination)
        return (
            "RL-001 supplier recovery request",
            (
                "Fictional demo — this message is not a purchase order or financial "
                "commitment.\n\n"
                f"Case reference: {decision.case_id}\n"
                f"Approved demo response: {option.name}.\n\n"
                f"Planned demo coordination:\n{coordination_text}\n\n"
                "Please confirm the current recovery timing and any remaining "
                "constraints affecting supply."
            ),
        )

    @staticmethod
    def _state(records) -> ReviewedSupplierEmail:
        return ReviewedSupplierEmail.from_records(*records)

    def get(self, decision_id: str) -> ReviewedSupplierEmail:
        with self._uow_factory() as uow:
            current = uow.mail.get_current(decision_id)
            if current is not None:
                return self._state(current)
            decision = guard_execution_current(uow, decision_id)
            self._require_current_projection(uow, decision)
            action = self._draft_action(uow, decision_id)
            actions = uow.execution.list_actions(decision_id=decision_id)
            subject, body = self._initial_content(decision, actions)
            now = self._clock()
            revision = SupplierEmailRevision(
                email_id=deterministic_email_id(decision_id),
                decision_id=decision_id,
                action_id=action.action_id,
                revision=1,
                subject=subject,
                body=body,
                from_address=self._from_address,
                to_address=self._to_address,
                edited_by=self._configured_actor,
                edited_at=now,
            )
            delivery = SupplierEmailDelivery(
                email_id=revision.email_id,
                decision_id=decision_id,
                status_updated_at=now,
            )
            uow.mail.insert_initial(revision, delivery)
            uow.commit()
            return self._state((revision, delivery))

    def save(
        self,
        decision_id: str,
        revision: int,
        subject: str,
        body: str,
        actor: IdentitySnapshot,
    ) -> ReviewedSupplierEmail:
        self._require_actor(actor)
        with self._uow_factory() as uow:
            decision = guard_execution_current(uow, decision_id)
            self._require_current_projection(uow, decision)
            self._draft_action(uow, decision_id)
            current = uow.mail.get_current(decision_id)
            if current is None:
                raise EmailStateError("Open the supplier email before editing it.")
            previous, delivery = current
            changed = SupplierEmailRevision(
                email_id=previous.email_id,
                decision_id=previous.decision_id,
                action_id=previous.action_id,
                revision=revision + 1,
                subject=subject,
                body=body,
                from_address=self._from_address,
                to_address=self._to_address,
                edited_by=actor,
                edited_at=self._clock(),
            )
            if not uow.mail.append_revision(changed, expected_revision=revision):
                raise EmailRevisionConflict(
                    "The supplier email changed. Refresh it and try again."
                )
            uow.commit()
            return self._state(
                (
                    changed,
                    delivery.model_copy(
                        update={
                            "reviewed_revision": None,
                            "send_status": "draft",
                            "status_updated_at": changed.edited_at,
                            "provider_message_id": None,
                            "internet_message_id": None,
                            "correlation_id": None,
                            "failure_code": None,
                        }
                    ),
                )
            )

    def review(
        self,
        decision_id: str,
        revision: int,
        actor: IdentitySnapshot,
    ) -> ReviewedSupplierEmail:
        self._require_actor(actor)
        with self._uow_factory() as uow:
            decision = guard_execution_current(uow, decision_id)
            self._require_current_projection(uow, decision)
            self._draft_action(uow, decision_id)
            current = uow.mail.get_current(decision_id)
            if current is None:
                raise EmailStateError("Open the supplier email before reviewing it.")
            previous, delivery = current
            if previous.revision != revision:
                raise EmailRevisionConflict(
                    "The supplier email changed. Refresh it and try again."
                )
            if previous.reviewed_by is not None:
                if (
                    previous.reviewed_by == actor
                    and delivery.reviewed_revision == revision
                ):
                    return self._state(current)
                raise EmailStateError(
                    "This supplier email revision is already reviewed."
                )
            now = self._clock()
            reviewed = previous.model_copy(
                update={"reviewed_by": actor, "reviewed_at": now}
            )
            reviewed_delivery = delivery.model_copy(
                update={"reviewed_revision": revision, "status_updated_at": now}
            )
            if not uow.mail.mark_reviewed(
                reviewed,
                reviewed_delivery,
                expected_revision=revision,
            ):
                raise EmailRevisionConflict(
                    "The supplier email changed. Refresh it and try again."
                )
            uow.commit()
            return self._state((reviewed, reviewed_delivery))

    def _send_records(
        self,
        uow,
        decision_id: str,
        revision: int,
        actor: object,
    ) -> tuple[SupplierEmailRevision, SupplierEmailDelivery]:
        self._require_actor(actor)  # type: ignore[arg-type]
        decision = guard_execution_current(uow, decision_id)
        self._require_current_projection(uow, decision)
        self._draft_action(uow, decision_id)
        current = uow.mail.get_current(decision_id)
        if current is None:
            raise EmailStateError("Open the supplier email before sending it.")
        content, delivery = current
        if content.revision != revision:
            raise EmailRevisionConflict(
                "The supplier email changed. Refresh it and try again."
            )
        if (
            content.reviewed_by is None
            or content.reviewed_at is None
            or delivery.reviewed_revision != revision
        ):
            raise EmailStateError(
                "Review the current supplier email before sending it."
            )
        return content, delivery

    def _canonical(self, decision_id: str) -> ReviewedSupplierEmail:
        with self._uow_factory() as uow:
            current = uow.mail.get_current(decision_id)
            if current is None:
                raise EmailStateError("The supplier email is not available.")
            return self._state(current)

    def _transition(
        self,
        decision_id: str,
        correlation_id: str,
        *,
        expected_statuses: tuple[str, ...],
        status: str,
        provider_message_id: str | None = None,
        internet_message_id: str | None = None,
        failure_code: str | None = None,
    ) -> ReviewedSupplierEmail:
        with self._uow_factory() as uow:
            current = uow.mail.get_current(decision_id)
            if current is None:
                raise EmailStateError("The supplier email is not available.")
            revision, delivery = current
            if delivery.correlation_id != correlation_id:
                return self._state(current)
            changed = delivery.model_copy(
                update={
                    "send_status": status,
                    "provider_message_id": (
                        provider_message_id
                        if provider_message_id is not None
                        else delivery.provider_message_id
                    ),
                    "internet_message_id": (
                        internet_message_id
                        if internet_message_id is not None
                        else delivery.internet_message_id
                    ),
                    "status_updated_at": self._clock(),
                    "failure_code": failure_code,
                }
            )
            if not uow.mail.update_delivery_state(
                changed,
                expected_correlation_id=correlation_id,
                expected_statuses=expected_statuses,
            ):
                return self._state(uow.mail.get_current(decision_id) or current)
            uow.commit()
            return self._state((revision, changed))

    async def send(
        self,
        decision_id: str,
        revision: int,
        actor: object,
    ) -> ReviewedSupplierEmail:
        if not self._mail_send_enabled or self._graph_mail is None:
            raise EmailSendDisabled("Supplier email sending is not enabled.")
        with self._uow_factory() as uow:
            content, delivery = self._send_records(uow, decision_id, revision, actor)
            if delivery.send_status not in ("draft", "failed"):
                return self._state((content, delivery))
            correlation_id = str(uuid4())
            claimed = delivery.model_copy(
                update={
                    "send_status": "submitting",
                    "provider_message_id": None,
                    "internet_message_id": None,
                    "correlation_id": correlation_id,
                    "status_updated_at": self._clock(),
                    "failure_code": None,
                }
            )
            if not uow.mail.claim_send(claimed, expected_revision=revision):
                return self._canonical(decision_id)
            uow.commit()

        try:
            await self._graph_mail.send_message(content, actor)
        except GraphMailSubmissionUncertain as error:
            return self._transition(
                decision_id,
                correlation_id,
                expected_statuses=("submitting",),
                status="uncertain",
                failure_code=error.code,
            )
        except GraphMailError as error:
            return self._transition(
                decision_id,
                correlation_id,
                expected_statuses=("submitting",),
                status="failed",
                failure_code=error.code,
            )
        return self._transition(
            decision_id,
            correlation_id,
            expected_statuses=("submitting",),
            status="accepted",
        )

    @staticmethod
    def _provider_matches(
        provider: ProviderMessage,
        revision: SupplierEmailRevision,
        delivery: SupplierEmailDelivery,
    ) -> bool:
        return (
            provider.provider_message_id == delivery.provider_message_id
            and (
                delivery.internet_message_id is None
                or provider.internet_message_id == delivery.internet_message_id
            )
            and provider.sender_address == revision.from_address
            and provider.to_addresses == (revision.to_address,)
            and provider.subject == revision.subject
            and provider.body_content_type == "text"
            and provider.body == revision.body
        )

    async def check_send_status(
        self,
        decision_id: str,
        actor: object,
    ) -> ReviewedSupplierEmail:
        if not self._mail_send_enabled or self._graph_mail is None:
            raise EmailSendDisabled("Supplier email sending is not enabled.")
        with self._uow_factory() as uow:
            current = uow.mail.get_current(decision_id)
            if current is None:
                raise EmailStateError("The supplier email is not available.")
            revision, delivery = current
            self._send_records(uow, decision_id, revision.revision, actor)
            if delivery.send_status == "sent-confirmed":
                return self._state(current)
            if (
                delivery.send_status not in ("submitting", "accepted", "uncertain")
                or delivery.provider_message_id is None
                or delivery.correlation_id is None
            ):
                raise EmailStateError("Send status is not available to check.")
        try:
            provider = await self._graph_mail.get_message(
                delivery.provider_message_id, actor
            )
        except GraphMailError:
            return self._canonical(decision_id)
        if not self._provider_matches(provider, revision, delivery):
            return self._transition(
                decision_id,
                delivery.correlation_id,
                expected_statuses=("submitting", "accepted", "uncertain"),
                status="uncertain",
                failure_code="graph_message_mismatch",
            )
        if provider.sent_at is None:
            return self._canonical(decision_id)
        return self._transition(
            decision_id,
            delivery.correlation_id,
            expected_statuses=("submitting", "accepted", "uncertain"),
            status="sent-confirmed",
        )
