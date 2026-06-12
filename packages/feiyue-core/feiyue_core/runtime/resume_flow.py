from __future__ import annotations

from pydantic import Field

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.schemas.common import FeiyueModel

from .journal import SessionJournal
from .reconciler import Reconciler, ReconciliationDecision, ReconciliationReport
from .recovery_prompt import RecoveryPromptBuilder
from .recovery_safety_gate import RecoverySafetyDecision, RecoverySafetyGate


class ResumeContext(FeiyueModel):
    manifest: RecoveryManifest
    report: ReconciliationReport
    recovery_prompt: str
    warnings: list[str] = Field(default_factory=list)
    safety_decision: RecoverySafetyDecision | None = None


class ResumeFlow:
    def __init__(
        self,
        journal: SessionJournal,
        reconciler: Reconciler | None = None,
        prompt_builder: RecoveryPromptBuilder | None = None,
        safety_gate: RecoverySafetyGate | None = None,
    ) -> None:
        self.journal = journal
        self.reconciler = reconciler or Reconciler(journal)
        self.prompt_builder = prompt_builder or RecoveryPromptBuilder()
        self.safety_gate = safety_gate or RecoverySafetyGate()

    def prepare(self) -> ResumeContext:
        manifest = self.journal.read_manifest()
        report = self.reconciler.reconcile()
        manifest.next_safe_action = report.next_safe_action
        for decision in report.decisions:
            if decision.decision == ReconciliationDecision.CONFIRMED:
                manifest.pending_operations = [op for op in manifest.pending_operations if op != decision.operation_id]
                manifest.operation_risk_levels.pop(decision.operation_id, None)
                output = f"operation {decision.operation_id} reconciled as confirmed"
                if decision.operation_id.startswith("operation "):
                    output = decision.operation_id
                if output not in manifest.verified_outputs:
                    manifest.verified_outputs.append(output)
                continue
            if decision.decision in {ReconciliationDecision.NEEDS_INSPECTION, ReconciliationDecision.UNSAFE_TO_REPEAT}:
                if decision.reason not in manifest.open_questions:
                    manifest.open_questions.append(decision.reason)
        safety_decision = self.safety_gate.evaluate(manifest)
        if not safety_decision.allowed:
            manifest.next_safe_action = "resolve high-risk pending/unknown side effects before continuing"
        self.journal.write_manifest(manifest)
        prompt = self.prompt_builder.build(manifest)
        warnings = [
            item.reason
            for item in report.decisions
            if item.decision in {ReconciliationDecision.NEEDS_INSPECTION, ReconciliationDecision.UNSAFE_TO_REPEAT}
        ]
        if not safety_decision.allowed:
            warnings.append(safety_decision.reason)
        return ResumeContext(
            manifest=manifest,
            report=report,
            recovery_prompt=prompt,
            warnings=warnings,
            safety_decision=safety_decision,
        )
