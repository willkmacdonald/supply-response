"""Policy and qualification constraint checks.

These checks are deterministic. They encode the rules that make Supplier Beta
non-executable in the RL-001 demo scenario, plus finance approval thresholds.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from data.schemas.models import (
    QualificationStatus,
    QualityQualification,
    ResponseScenario,
)

POLICY_VERSION = "1.0.0"

#: Premium freight above this amount requires a finance approver.
PREMIUM_FREIGHT_APPROVAL_THRESHOLD = 25_000.0

#: Any response above this amount requires finance approval regardless of type.
RESPONSE_COST_APPROVAL_THRESHOLD = 50_000.0


class PolicyViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    blocking: bool = True
    source_reference: str = ""
    expected_resolution_date: Optional[date] = None


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str = POLICY_VERSION
    executable: bool = True
    requires_approval: bool = False
    approver_roles: list[str] = Field(default_factory=list)
    violations: list[PolicyViolation] = Field(default_factory=list)
    conditional: bool = False
    notes: list[str] = Field(default_factory=list)

    @property
    def blocking_constraint(self) -> Optional[str]:
        for violation in self.violations:
            if violation.blocking:
                return violation.message
        return None


def find_qualification(
    qualifications: Iterable[QualityQualification],
    supplier_id: str,
    part_id: str,
) -> Optional[QualityQualification]:
    for qualification in qualifications:
        if qualification.supplier_id == supplier_id and qualification.part_id == part_id:
            return qualification
    return None


def check_supplier_qualification(
    qualifications: Iterable[QualityQualification],
    supplier_id: str,
    part_id: str,
) -> PolicyDecision:
    """Is ``supplier_id`` approved to supply ``part_id`` right now?"""
    qualification = find_qualification(qualifications, supplier_id, part_id)
    if qualification is None:
        return PolicyDecision(
            executable=False,
            violations=[
                PolicyViolation(
                    code="QUALITY_NO_RECORD",
                    message=(
                        f"No quality qualification record exists for {supplier_id} "
                        f"and {part_id}."
                    ),
                    blocking=True,
                )
            ],
        )

    if qualification.status == QualificationStatus.APPROVED:
        return PolicyDecision(
            executable=True,
            notes=[f"{qualification.qualification_id}: supplier approved for {part_id}."],
        )

    missing: list[str] = []
    if not qualification.audit_complete:
        missing.append("supplier audit incomplete")
    if not qualification.first_article_complete:
        missing.append("first-article approval incomplete")
    detail = "; ".join(missing) if missing else qualification.status.value

    return PolicyDecision(
        executable=False,
        conditional=qualification.status
        in (QualificationStatus.CONDITIONAL, QualificationStatus.NOT_APPROVED),
        violations=[
            PolicyViolation(
                code="QUALITY_NOT_APPROVED",
                message=(
                    f"{qualification.qualification_id}: supplier {supplier_id} is not "
                    f"approved for {part_id} ({detail})."
                ),
                blocking=True,
                source_reference=qualification.source_reference
                or qualification.qualification_id,
                expected_resolution_date=qualification.expected_decision_date,
            )
        ],
        notes=[qualification.note] if qualification.note else [],
    )


def check_spend_approval(cost: float, premium_freight_cost: float = 0.0) -> PolicyDecision:
    """Approval routing based on response cost and premium freight spend."""
    decision = PolicyDecision(executable=True)
    if premium_freight_cost > PREMIUM_FREIGHT_APPROVAL_THRESHOLD:
        decision.requires_approval = True
        decision.approver_roles.append("finance_approver")
        decision.violations.append(
            PolicyViolation(
                code="PREMIUM_FREIGHT_THRESHOLD",
                message=(
                    f"Premium freight of {premium_freight_cost:,.2f} exceeds the "
                    f"{PREMIUM_FREIGHT_APPROVAL_THRESHOLD:,.2f} approval threshold."
                ),
                blocking=False,
            )
        )
    if cost > RESPONSE_COST_APPROVAL_THRESHOLD:
        decision.requires_approval = True
        if "finance_approver" not in decision.approver_roles:
            decision.approver_roles.append("finance_approver")
        decision.violations.append(
            PolicyViolation(
                code="RESPONSE_COST_THRESHOLD",
                message=(
                    f"Response cost of {cost:,.2f} exceeds the "
                    f"{RESPONSE_COST_APPROVAL_THRESHOLD:,.2f} approval threshold."
                ),
                blocking=False,
            )
        )
    if cost > 0 and not decision.requires_approval:
        decision.requires_approval = True
        decision.approver_roles.append("material_planner")
    return decision


def merge_decisions(*decisions: PolicyDecision) -> PolicyDecision:
    merged = PolicyDecision()
    roles: list[str] = []
    for decision in decisions:
        merged.executable = merged.executable and decision.executable
        merged.requires_approval = merged.requires_approval or decision.requires_approval
        merged.conditional = merged.conditional or decision.conditional
        merged.violations.extend(decision.violations)
        merged.notes.extend(decision.notes)
        for role in decision.approver_roles:
            if role not in roles:
                roles.append(role)
    merged.approver_roles = roles
    return merged


def check_scenario(
    scenario: ResponseScenario,
    qualifications: Sequence[QualityQualification],
    cost: float = 0.0,
    premium_freight_cost: float = 0.0,
) -> PolicyDecision:
    """Evaluate every policy that applies to a candidate response scenario."""
    decisions = [check_spend_approval(cost, premium_freight_cost)]
    if scenario.alternate_supplier_id:
        decisions.append(
            check_supplier_qualification(
                qualifications, scenario.alternate_supplier_id, _scenario_part(scenario)
            )
        )
    return merge_decisions(*decisions)


def _scenario_part(scenario: ResponseScenario) -> str:
    """Part id carried on the scenario assumptions, if present."""
    for assumption in scenario.assumptions:
        if assumption.startswith("part_id="):
            return assumption.split("=", 1)[1]
    return ""


__all__ = [
    "POLICY_VERSION",
    "PREMIUM_FREIGHT_APPROVAL_THRESHOLD",
    "RESPONSE_COST_APPROVAL_THRESHOLD",
    "PolicyDecision",
    "PolicyViolation",
    "check_scenario",
    "check_spend_approval",
    "check_supplier_qualification",
    "find_qualification",
    "merge_decisions",
]
