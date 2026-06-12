from __future__ import annotations

from .journal import SessionJournal
from .operation_recorder import OperationRecorder
from .reconciler import Reconciler, ReconciliationDecision, ReconciliationItem, ReconciliationReport
from .recovery_prompt import RecoveryPromptBuilder
from .recovery_safety_gate import RecoverySafetyDecision, RecoverySafetyGate
from .resume_flow import ResumeContext, ResumeFlow
from .side_effect_inspector import SideEffectCheck, SideEffectInspector, SideEffectStatus

__all__ = [
    "OperationRecorder",
    "InterruptionSimulationResult",
    "Reconciler",
    "ReconciliationDecision",
    "ReconciliationItem",
    "ReconciliationReport",
    "RecoveryPromptBuilder",
    "RecoverySafetyDecision",
    "RecoverySafetyGate",
    "ResumeContext",
    "ResumeFlow",
    "SessionJournal",
    "SideEffectCheck",
    "SideEffectInspector",
    "SideEffectStatus",
    "simulate_interrupted_resume",
]


def __getattr__(name: str):
    if name in {"InterruptionSimulationResult", "simulate_interrupted_resume"}:
        from .interruption_simulation import InterruptionSimulationResult, simulate_interrupted_resume

        return {
            "InterruptionSimulationResult": InterruptionSimulationResult,
            "simulate_interrupted_resume": simulate_interrupted_resume,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
