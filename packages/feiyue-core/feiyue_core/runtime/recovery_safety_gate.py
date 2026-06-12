from __future__ import annotations

from pydantic import Field

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.schemas.common import FeiyueModel


class RecoverySafetyDecision(FeiyueModel):
    allowed: bool
    reason: str
    blocked_operations: list[str] = Field(default_factory=list)


class RecoverySafetyGate:
    """Block unsafe continuation when high-risk side effects remain unresolved."""

    high_risk_levels = {"high"}

    def evaluate(self, manifest: RecoveryManifest) -> RecoverySafetyDecision:
        blocked = [
            operation_id
            for operation_id in manifest.pending_operations
            if manifest.operation_risk_levels.get(operation_id) in self.high_risk_levels
        ]
        if blocked:
            operations = ", ".join(blocked)
            return RecoverySafetyDecision(
                allowed=False,
                blocked_operations=blocked,
                reason=f"blocked high-risk pending/unknown side effect operations: {operations}",
            )
        return RecoverySafetyDecision(
            allowed=True,
            blocked_operations=[],
            reason="no high-risk pending/unknown side effects remain",
        )
