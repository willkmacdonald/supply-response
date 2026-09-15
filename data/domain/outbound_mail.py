from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from data.domain.common import FrozenModel
from data.domain.decisions import IdentitySnapshot

SupplierEmailSendStatus = Literal[
    "draft",
    "submitting",
    "accepted",
    "sent-confirmed",
    "failed",
    "uncertain",
]


class SupplierEmailRevision(FrozenModel):
    email_id: str
    decision_id: str
    action_id: str
    revision: int = Field(gt=0)
    subject: str = Field(max_length=255)
    body: str = Field(max_length=10_000)
    from_address: str = Field(max_length=320)
    to_address: str = Field(max_length=320)
    edited_by: IdentitySnapshot
    edited_at: datetime
    reviewed_by: IdentitySnapshot | None = None
    reviewed_at: datetime | None = None

    @field_validator(
        "email_id",
        "decision_id",
        "action_id",
        "subject",
        "body",
        "from_address",
        "to_address",
    )
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("supplier email fields must be nonblank")
        return value

    @field_validator("from_address", "to_address")
    @classmethod
    def require_email_shape(cls, value: str) -> str:
        local, separator, domain = value.partition("@")
        if (
            not separator
            or not local
            or not domain
            or any(character.isspace() for character in value)
        ):
            raise ValueError("supplier email address is invalid")
        return value.lower()

    @model_validator(mode="after")
    def require_complete_review(self) -> SupplierEmailRevision:
        if (self.reviewed_by is None) != (self.reviewed_at is None):
            raise ValueError(
                "supplier email review actor and time must be recorded together"
            )
        return self


class SupplierEmailDelivery(FrozenModel):
    email_id: str
    decision_id: str
    reviewed_revision: int | None = Field(default=None, gt=0)
    send_status: SupplierEmailSendStatus = "draft"
    provider_message_id: str | None = None
    internet_message_id: str | None = None
    correlation_id: str | None = None
    status_updated_at: datetime
    failure_code: str | None = None

    @field_validator("email_id", "decision_id")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("supplier email delivery identity must be nonblank")
        return value


class ReviewedSupplierEmail(FrozenModel):
    email_id: str
    decision_id: str
    action_id: str
    revision: int
    subject: str
    body: str
    from_address: str
    to_address: str
    reviewed_revision: int | None
    reviewed_at: datetime | None
    reviewed_by: IdentitySnapshot | None
    send_status: SupplierEmailSendStatus

    @classmethod
    def from_records(
        cls,
        revision: SupplierEmailRevision,
        delivery: SupplierEmailDelivery,
    ) -> ReviewedSupplierEmail:
        effective_review = delivery.reviewed_revision == revision.revision
        return cls(
            email_id=revision.email_id,
            decision_id=revision.decision_id,
            action_id=revision.action_id,
            revision=revision.revision,
            subject=revision.subject,
            body=revision.body,
            from_address=revision.from_address,
            to_address=revision.to_address,
            reviewed_revision=(
                delivery.reviewed_revision if effective_review else None
            ),
            reviewed_at=revision.reviewed_at if effective_review else None,
            reviewed_by=revision.reviewed_by if effective_review else None,
            send_status=delivery.send_status,
        )
