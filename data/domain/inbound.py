"""Immutable reviewed email provenance and bounded supplier statement facts."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field

from .common import FrozenModel, Money

if TYPE_CHECKING:
    from data.synthetic.rl001 import OperationalSnapshot


class InboundEmailError(ValueError):
    def __init__(self, code: str = "INBOUND_EMAIL_UNSUPPORTED") -> None:
        self.code = code
        super().__init__(code)


class SupplierDisruptionFacts(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    original_quantity: int = Field(gt=0)
    part_id: str
    plant_name: str
    original_due_date: date
    partial_quantity: int = Field(gt=0)
    partial_due_date: date
    additional_cost_per_unit: Money = Field(ge=0)
    remaining_quantity: int = Field(gt=0)
    recovery_date: date | None = None


class SupplierEmailSource(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    mailbox_object_id: str
    internet_message_id: str = Field(min_length=3, max_length=998)
    review_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    message_id: str
    subject: str
    sender: str
    recipients: tuple[str, ...]
    received_at: datetime
    reviewed_at: datetime
    citation_url: str
    facts: SupplierDisruptionFacts


_QUANTITY = r"(?:[1-9][0-9]{0,8}|[1-9][0-9]{0,2}(?:,[0-9]{3}){1,2})"
_DATE = r"(?:[A-Za-z]+ [0-9]{1,2}, [0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})"
_STATEMENT = re.compile(
    rf"Supplier Alpha cannot deliver (?P<original>{_QUANTITY}) units of "
    rf"(?P<part>RL-MAT-[0-9]+) (?:to|at) (?P<plant>Chicago) on (?P<due>{_DATE})\. "
    rf"We can offer a partial shipment of (?P<partial>{_QUANTITY}) units by air "
    rf"arriving (?P<partial_due>{_DATE}), at an additional USD (?P<cost>[0-9]+\.[0-9]{{2}}) per unit\. "
    rf"The remaining (?P<remaining>{_QUANTITY}) units have no confirmed delivery date\.",
    re.IGNORECASE,
)
_WILL_STATEMENT = re.compile(
    rf"(?:FYI )?Supplier Alpha cannot deliver the (?P<original>{_QUANTITY}) units of component "
    rf"(?P<part>RL-MAT-[0-9]+) originally due at the (?P<plant>Chicago) plant on (?P<due>{_DATE})\. "
    rf"We can offer a partial shipment of (?P<partial>{_QUANTITY}) units by air on "
    rf"(?P<partial_due>[A-Za-z]+ [0-9]{{1,2}}(?:, [0-9]{{4}})?) at an additional cost of "
    rf"\$(?P<cost>[0-9]+\.[0-9]{{2}}) per unit\. "
    rf"We do not have a confirmed delivery date for the remaining (?P<remaining>{_QUANTITY}) units\.",
    re.IGNORECASE,
)


def _date(value: str) -> date:
    return (
        date.fromisoformat(value)
        if value[0].isdigit()
        else datetime.strptime(value, "%B %d, %Y").date()  # noqa: DTZ007 - calendar date, no instant
    )


def parse_supplier_disruption(text: str) -> SupplierDisruptionFacts:
    """Recognize one entire inert statement, never instructions or inferred values."""
    if not isinstance(text, str) or len(text) > 16000:
        raise InboundEmailError()
    normalized = " ".join(text.split())
    match = _STATEMENT.fullmatch(normalized) or _WILL_STATEMENT.fullmatch(normalized)
    if match is None:
        raise InboundEmailError()
    values = match.groupdict()
    try:
        original, partial, remaining = (
            int(values[key].replace(",", ""))
            for key in ("original", "partial", "remaining")
        )
        due = _date(values["due"])
        partial_due = values["partial_due"]
        # The supported supplier template omits the year for the second date.
        # Resolve it within the explicitly stated original delivery year only.
        if not partial_due[0].isdigit() and "," not in partial_due:
            partial_due = f"{partial_due}, {due.year}"
        facts = SupplierDisruptionFacts(
            original_quantity=original,
            part_id=values["part"].upper(),
            plant_name="Chicago",
            original_due_date=due,
            partial_quantity=partial,
            partial_due_date=_date(partial_due),
            additional_cost_per_unit=Decimal(values["cost"]),
            remaining_quantity=remaining,
        )
        if (
            original != partial + remaining
            or facts.partial_due_date < facts.original_due_date
        ):
            raise ValueError()
    except ValueError:
        raise InboundEmailError() from None
    return facts


def validate_supplier_facts(
    facts: SupplierDisruptionFacts, snapshot: OperationalSnapshot
) -> None:
    disruption, option = snapshot.disruption, snapshot.alpha_expedite
    if (
        option is None
        or disruption.supplier_id != "RL-SUP-ALPHA"
        or facts.part_id != disruption.part_id
        or facts.plant_name != "Chicago"
        or disruption.plant_id != "RL-PLANT-CHI"
        or facts.original_quantity != disruption.original_quantity
        or facts.original_due_date != disruption.original_due_date
        or disruption.partial_quantity != 0
        or disruption.partial_due_date is not None
        or facts.recovery_date != disruption.recovery_date
        or facts.recovery_date is not None
        or facts.remaining_quantity != facts.original_quantity - facts.partial_quantity
        or option.supplier_id != disruption.supplier_id
        or option.part_id != disruption.part_id
        or option.plant_id != disruption.plant_id
        or option.quantity != facts.partial_quantity
        or option.due_date != facts.partial_due_date
        or option.incremental_cost_per_unit != facts.additional_cost_per_unit
    ):
        raise InboundEmailError("INBOUND_EMAIL_CONFLICT")
