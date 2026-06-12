from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from feiyue_core.audit import JsonlTraceWriter
from feiyue_core.candidates import CandidateRevisionLoop, FeedbackAnalyzer, VerificationFeedback
from feiyue_core.routing import TeacherInterventionContext
from feiyue_core.schemas import Candidate, CandidateStatus, StrategyVersion, TaskSpec, TraceEvent, TraceEventType, VerificationResult
from feiyue_core.schemas.common import FeiyueModel

from .candidate_service import CandidateService, CandidateServiceResult


class CandidateVerifier(Protocol):
    def verify(self, candidate: Candidate) -> VerificationResult: ...


class ToyIterationResult(FeiyueModel):
    passed: bool
    final_candidate: Candidate
    candidates: list[Candidate] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    feedback: list[VerificationFeedback] = Field(default_factory=list)
    teacher_guidance_events: list[dict[str, object]] = Field(default_factory=list)


class ToyIterationLoop:
    def __init__(
        self,
        *,
        candidate_service: CandidateService,
        verifier: CandidateVerifier,
        feedback_analyzer: FeedbackAnalyzer | None = None,
        revision_loop: CandidateRevisionLoop | None = None,
        trace_writer: JsonlTraceWriter | None = None,
        session_id: str = "toy_iteration_loop",
    ) -> None:
        self.candidate_service = candidate_service
        self.verifier = verifier
        self.feedback_analyzer = feedback_analyzer or FeedbackAnalyzer()
        self.revision_loop = revision_loop or CandidateRevisionLoop()
        self.trace_writer = trace_writer
        self.session_id = session_id
        self._event_index = 0

    def run(
        self,
        *,
        task: TaskSpec,
        strategy: StrategyVersion,
        initial_file_writes: dict[str, str],
        revised_file_writes: dict[str, str],
        max_attempts: int = 2,
    ) -> ToyIterationResult:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        candidates: list[Candidate] = []
        verification_results: list[VerificationResult] = []
        feedback_items: list[VerificationFeedback] = []
        teacher_guidance_events: list[dict[str, object]] = []

        service_result = self.candidate_service.generate_candidate(
            task=task,
            strategy=strategy,
            intervention_context=TeacherInterventionContext(task_id=task.id, student_failure_count=0),
            provider_metadata={"file_writes": initial_file_writes},
        )
        if service_result.candidate is None:
            raise RuntimeError("student candidate service did not return a candidate")
        current_candidate = service_result.candidate
        self._emit_candidate_generated(task=task, candidate=current_candidate, service_result=service_result)

        for attempt_index in range(max_attempts):
            candidates.append(current_candidate)
            verification_result = self.verifier.verify(current_candidate)
            verification_results.append(verification_result)
            self._emit_verification(candidate=current_candidate, verification_result=verification_result)

            feedback = self.feedback_analyzer.analyze(verification_result)
            feedback_items.append(feedback)
            current_candidate.metadata["verification_result_id"] = verification_result.id
            current_candidate.metadata["verification_passed"] = verification_result.passed
            self._emit_feedback(task=task, candidate=current_candidate, feedback=feedback)

            if verification_result.passed:
                current_candidate.status = CandidateStatus.VERIFIED
                result = ToyIterationResult(
                    passed=True,
                    final_candidate=current_candidate,
                    candidates=candidates,
                    verification_results=verification_results,
                    feedback=feedback_items,
                    teacher_guidance_events=teacher_guidance_events,
                )
                self._emit_iteration_completed(task=task, result=result)
                return result

            if attempt_index == max_attempts - 1:
                current_candidate.status = CandidateStatus.FAILED
                result = ToyIterationResult(
                    passed=False,
                    final_candidate=current_candidate,
                    candidates=candidates,
                    verification_results=verification_results,
                    feedback=feedback_items,
                    teacher_guidance_events=teacher_guidance_events,
                )
                self._emit_iteration_completed(task=task, result=result)
                return result

            teacher_result = self.candidate_service.generate_candidate(
                task=task,
                strategy=strategy,
                intervention_context=TeacherInterventionContext(
                    task_id=task.id,
                    student_failure_count=attempt_index + 1,
                    failure_category=feedback.category,
                    verifier_confidence=verification_result.confidence,
                    teacher_calls_used=len(teacher_guidance_events),
                    teacher_call_budget=1,
                ),
                provider_metadata={"failure_category": feedback.category, "evidence_excerpt": feedback.evidence_excerpt},
            )
            teacher_guidance = teacher_result.teacher_guidance
            if teacher_guidance is not None:
                teacher_guidance_events.append(teacher_guidance)
                self._emit_teacher_guidance(task=task, candidate=current_candidate, teacher_result=teacher_result)

            revised_candidate = self.revision_loop.revise(
                task=task,
                strategy=strategy,
                parent=current_candidate,
                feedback=feedback,
                revised_file_writes=revised_file_writes,
            )
            if teacher_guidance is not None:
                revised_candidate.metadata["teacher_guidance"] = teacher_guidance
                revised_candidate.metadata["teacher_trigger"] = teacher_result.routing_decision.trigger.value
                revised_candidate.metadata["teacher_request_id"] = teacher_result.provider_response.request_id
            self._emit_candidate_revised(task=task, parent=current_candidate, revised=revised_candidate, feedback=feedback)
            current_candidate = revised_candidate

        raise RuntimeError("iteration loop exited unexpectedly")

    def _emit_candidate_generated(self, *, task: TaskSpec, candidate: Candidate, service_result: CandidateServiceResult) -> None:
        self._emit(
            TraceEventType.CANDIDATE_GENERATED,
            "candidate generated",
            {
                "task_id": task.id,
                "candidate_id": candidate.id,
                "prompt_template_hash": candidate.metadata.get("prompt_template_hash"),
                "prompt_rendered_hash": candidate.metadata.get("prompt_rendered_hash"),
                "provider_request_id": candidate.metadata.get("request_id"),
                "routing_trigger": service_result.routing_decision.trigger.value,
            },
        )

    def _emit_verification(self, *, candidate: Candidate, verification_result: VerificationResult) -> None:
        event_type = TraceEventType.VERIFICATION_PASSED if verification_result.passed else TraceEventType.VERIFICATION_FAILED
        self._emit(
            event_type,
            "verification passed" if verification_result.passed else "verification failed",
            {
                "candidate_id": candidate.id,
                "verification_result_id": verification_result.id,
                "verifier_name": verification_result.verifier_name,
                "failure_category": verification_result.failure_category,
                "confidence": verification_result.confidence,
            },
        )

    def _emit_feedback(self, *, task: TaskSpec, candidate: Candidate, feedback: VerificationFeedback) -> None:
        self._emit(
            TraceEventType.FEEDBACK_ANALYZED,
            "feedback analyzed",
            {
                "task_id": task.id,
                "candidate_id": candidate.id,
                "verification_result_id": feedback.verification_result_id,
                "passed": feedback.passed,
                "feedback_category": feedback.category,
                "action_items": feedback.action_items,
            },
        )

    def _emit_teacher_guidance(self, *, task: TaskSpec, candidate: Candidate, teacher_result: CandidateServiceResult) -> None:
        self._emit(
            TraceEventType.TEACHER_GUIDANCE_REQUESTED,
            "teacher guidance requested",
            {
                "task_id": task.id,
                "candidate_id": candidate.id,
                "provider_request_id": teacher_result.provider_response.request_id,
                "teacher_trigger": teacher_result.routing_decision.trigger.value,
                "teacher_model": teacher_result.provider_response.model,
            },
        )

    def _emit_candidate_revised(
        self, *, task: TaskSpec, parent: Candidate, revised: Candidate, feedback: VerificationFeedback
    ) -> None:
        self._emit(
            TraceEventType.CANDIDATE_REVISED,
            "candidate revised",
            {
                "task_id": task.id,
                "candidate_id": revised.id,
                "parent_candidate_id": parent.id,
                "revision_index": revised.metadata.get("revision_index"),
                "feedback_category": feedback.category,
            },
        )

    def _emit_iteration_completed(self, *, task: TaskSpec, result: ToyIterationResult) -> None:
        self._emit(
            TraceEventType.ITERATION_COMPLETED,
            "iteration completed",
            {
                "task_id": task.id,
                "passed": result.passed,
                "final_candidate_id": result.final_candidate.id,
                "final_candidate_status": result.final_candidate.status.value,
                "candidate_count": len(result.candidates),
                "verification_count": len(result.verification_results),
                "teacher_guidance_count": len(result.teacher_guidance_events),
            },
        )

    def _emit(self, event_type: TraceEventType, message: str, data: dict[str, Any]) -> None:
        if self.trace_writer is None:
            return
        self._event_index += 1
        self.trace_writer.append(
            TraceEvent(
                id=f"evt_{self.session_id}_{self._event_index:04d}",
                session_id=self.session_id,
                type=event_type,
                message=message,
                data=data,
            )
        )
