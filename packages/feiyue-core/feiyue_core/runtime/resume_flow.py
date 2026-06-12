from __future__ import annotations

from pydantic import Field

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.schemas.common import FeiyueModel

from .journal import SessionJournal
from .reconciler import Reconciler, ReconciliationDecision, ReconciliationReport
from .recovery_prompt import RecoveryPromptBuilder


class ResumeContext(FeiyueModel):
    manifest: RecoveryManifest
    report: ReconciliationReport
    recovery_prompt: str
    warnings: list[str] = Field(default_factory=list)


class ResumeFlow:
    def __init__(
        self,
        journal: SessionJournal,
        reconciler: Reconciler | None = None,
        prompt_builder: RecoveryPromptBuilder | None = None,
    ) -> None:
        self.journal = journal
        self.reconciler = reconciler or Reconciler(journal)
        self.prompt_builder = prompt_builder or RecoveryPromptBuilder()

    def prepare(self) -> ResumeContext:
        manifest = self.journal.read_manifest()
        report = self.reconciler.reconcile()
        manifest.next_safe_action = report.next_safe_action
        for decision in report.decisions:
            if decision.decision == ReconciliationDecision.CONFIRMED:
                manifest.pending_operations = [op for op in manifest.pending_operations if op != decision.operation_id]
                output = f"operation {decision.operation_id} reconciled as confirmed"
                if decision.operation_id.startswith("operation "):
                    output = decision.operation_id
                if output not in manifest.verified_outputs:
                    manifest.verified_outputs.append(output)
                continue
            if decision.decision in {ReconciliationDecision.NEEDS_INSPECTION, ReconciliationDecision.UNSAFE_TO_REPEAT}:
                if decision.reason not in manifest.open_questions:
                    manifest.open_questions.append(decision.reason)
        self.journal.write_manifest(manifest)
        prompt = self.prompt_builder.build(manifest)
        warnings = [
            item.reason
            for item in report.decisions
            if item.decision in {ReconciliationDecision.NEEDS_INSPECTION, ReconciliationDecision.UNSAFE_TO_REPEAT}
        ]
        return ResumeContext(manifest=manifest, report=report, recovery_prompt=prompt, warnings=warnings)
