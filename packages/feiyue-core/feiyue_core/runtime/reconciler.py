from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel

from .journal import SessionJournal


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
    def __init__(self, journal: SessionJournal) -> None:
        self.journal = journal

    def reconcile(self) -> ReconciliationReport:
        manifest = self.journal.read_manifest()
        decisions: list[ReconciliationItem] = []

        for operation_id in manifest.pending_operations:
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
