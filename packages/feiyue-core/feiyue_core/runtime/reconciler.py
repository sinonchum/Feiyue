from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel

from .journal import SessionJournal
from .side_effect_inspector import SideEffectInspector, SideEffectStatus


class ReconciliationDecision(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_INSPECTION = "needs_inspection"
    UNSAFE_TO_REPEAT = "unsafe_to_repeat"
    SAFE_TO_RETRY = "safe_to_retry"


class ReconciliationItem(FeiyueModel):
    operation_id: str
    decision: ReconciliationDecision
    reason: str


class ReconciliationReport(FeiyueModel):
    decisions: list[ReconciliationItem] = Field(default_factory=list)
    next_safe_action: str
    summary: str


class Reconciler:
    def __init__(self, journal: SessionJournal, inspector: SideEffectInspector | None = None) -> None:
        self.journal = journal
        self.inspector = inspector or SideEffectInspector()

    def reconcile(self) -> ReconciliationReport:
        manifest = self.journal.read_manifest()
        decisions: list[ReconciliationItem] = []

        for operation_id in manifest.pending_operations:
            checks = manifest.side_effect_checks.get(operation_id, [])
            if checks:
                decisions.append(self._decision_from_side_effect_checks(operation_id, checks))
                continue
            reason = self._reason_for_pending(operation_id, manifest.open_questions)
            decisions.append(
                ReconciliationItem(
                    operation_id=operation_id,
                    decision=ReconciliationDecision.NEEDS_INSPECTION,
                    reason=reason,
                )
            )

        for index, item in enumerate(manifest.do_not_repeat, start=1):
            decisions.append(
                ReconciliationItem(
                    operation_id=f"do_not_repeat:{index}",
                    decision=ReconciliationDecision.UNSAFE_TO_REPEAT,
                    reason=item,
                )
            )

        for output in manifest.verified_outputs:
            if output.startswith("operation ") and " finished" in output:
                decisions.append(
                    ReconciliationItem(
                        operation_id=output,
                        decision=ReconciliationDecision.CONFIRMED,
                        reason="verified output recorded in manifest",
                    )
                )

        next_safe_action = (
            "inspect pending/unknown operations before continuing"
            if any(item.decision in {ReconciliationDecision.NEEDS_INSPECTION, ReconciliationDecision.UNSAFE_TO_REPEAT} for item in decisions)
            else "continue with next planned step"
        )
        summary = self._summary(decisions)
        return ReconciliationReport(decisions=decisions, next_safe_action=next_safe_action, summary=summary)

    def _decision_from_side_effect_checks(self, operation_id: str, checks: list[dict[str, object]]) -> ReconciliationItem:
        results = [self.inspector.inspect(check) for check in checks]
        reason = "; ".join(f"{result.subject}: {result.reason}" for result in results)
        if any(result.status == SideEffectStatus.UNSAFE_TO_REPEAT for result in results):
            decision = ReconciliationDecision.UNSAFE_TO_REPEAT
        elif all(result.status == SideEffectStatus.CONFIRMED for result in results):
            decision = ReconciliationDecision.CONFIRMED
        else:
            decision = ReconciliationDecision.NEEDS_INSPECTION
        return ReconciliationItem(operation_id=operation_id, decision=decision, reason=reason)

    @staticmethod
    def _reason_for_pending(operation_id: str, open_questions: list[str]) -> str:
        for question in open_questions:
            if operation_id in question:
                return question
        return "operation is still pending in recovery manifest"

    @staticmethod
    def _summary(decisions: list[ReconciliationItem]) -> str:
        if not decisions:
            return "No pending, unknown, or unsafe operations found."
        counts: dict[str, int] = {}
        for item in decisions:
            counts[item.decision.value] = counts.get(item.decision.value, 0) + 1
        parts = [f"{key}={counts[key]}" for key in sorted(counts)]
        operation_ids = ", ".join(item.operation_id for item in decisions)
        return f"Reconciliation decisions: {'; '.join(parts)}. Operations: {operation_ids}."
