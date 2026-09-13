from uuid import UUID

from pydantic import model_validator

from data.domain.common import FrozenModel
from data.domain.decisions import IdentitySnapshot
from data.domain.evidence import IdentitySource


class FinancePermissionDenied(PermissionError):
    pass


class BoundFinanceActors(FrozenModel):
    tenant_id: UUID
    alex_object_id: UUID
    taylor_object_id: UUID

    @model_validator(mode="after")
    def different_people(self):
        if self.alex_object_id == self.taylor_object_id:
            raise ValueError("Alex and Taylor must be different people")
        return self

    def _require(self, actor: IdentitySnapshot, *, taylor: bool) -> None:
        name = "TAYLOR" if taylor else "ALEX"
        roles = (
            ("finance_approver",)
            if taylor
            else ("material_planner", "response_approver")
        )
        try:
            tenant = UUID(actor.tenant_id or "")
            object_id = UUID(actor.object_id or "")
        except (ValueError, TypeError, AttributeError) as error:
            raise FinancePermissionDenied(
                "Exact configured Finance workflow identity required"
            ) from error
        if (
            tenant != self.tenant_id
            or object_id != (self.taylor_object_id if taylor else self.alex_object_id)
            or actor.identity_source is not IdentitySource.ENTRA
            or actor.persona_id != f"RL-PERSONA-{name}"
            or actor.source_id != f"RL-ENTRA-{name}"
            or actor.effective_roles != roles
        ):
            raise FinancePermissionDenied(
                "Exact configured Finance workflow identity required"
            )

    def require_alex(self, actor: IdentitySnapshot) -> None:
        self._require(actor, taylor=False)

    def require_taylor(self, actor: IdentitySnapshot) -> None:
        self._require(actor, taylor=True)


def authority_material(actor: IdentitySnapshot) -> dict:
    return {
        "tenant_id": str(UUID(actor.tenant_id or "")),
        "object_id": str(UUID(actor.object_id or "")),
        "identity_source": actor.identity_source.value,
        "persona_id": actor.persona_id,
        "source_id": actor.source_id,
        "effective_roles": actor.effective_roles,
    }
