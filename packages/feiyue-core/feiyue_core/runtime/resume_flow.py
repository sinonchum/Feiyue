from __future__ import annotations

from pydantic import Field

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.schemas.common import FeiyueModel

from .journal import SessionJournal
from .reconciler import Reconciler, ReconciliationReport
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
            if decision.decision.value in {"needs_inspection", "unsafe_to_repeat"}:
                if decision.reason not in manifest.open_questions:
                    manifest.open_questions.append(decision.reason)
        prompt = self.prompt_builder.build(manifest)
        warnings = [item.reason for item in report.decisions if item.decision.value in {"needs_inspection", "unsafe_to_repeat"}]
        return ResumeContext(manifest=manifest, report=report, recovery_prompt=prompt, warnings=warnings)
