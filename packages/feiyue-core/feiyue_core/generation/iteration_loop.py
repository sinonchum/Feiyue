from __future__ import annotations

from typing import Protocol

from pydantic import Field

from feiyue_core.candidates import CandidateRevisionLoop, FeedbackAnalyzer, VerificationFeedback
from feiyue_core.routing import TeacherInterventionContext
from feiyue_core.schemas import Candidate, CandidateStatus, StrategyVersion, TaskSpec, VerificationResult
from feiyue_core.schemas.common import FeiyueModel

from .candidate_service import CandidateService


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
    ) -> None:
        self.candidate_service = candidate_service
        self.verifier = verifier
        self.feedback_analyzer = feedback_analyzer or FeedbackAnalyzer()
        self.revision_loop = revision_loop or CandidateRevisionLoop()

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

        for attempt_index in range(max_attempts):
            candidates.append(current_candidate)
            verification_result = self.verifier.verify(current_candidate)
            verification_results.append(verification_result)
            feedback = self.feedback_analyzer.analyze(verification_result)
            feedback_items.append(feedback)
            current_candidate.metadata["verification_result_id"] = verification_result.id
            current_candidate.metadata["verification_passed"] = verification_result.passed

            if verification_result.passed:
                current_candidate.status = CandidateStatus.VERIFIED
                return ToyIterationResult(
                    passed=True,
                    final_candidate=current_candidate,
                    candidates=candidates,
                    verification_results=verification_results,
                    feedback=feedback_items,
                    teacher_guidance_events=teacher_guidance_events,
                )

            if attempt_index == max_attempts - 1:
                current_candidate.status = CandidateStatus.FAILED
                return ToyIterationResult(
                    passed=False,
                    final_candidate=current_candidate,
                    candidates=candidates,
                    verification_results=verification_results,
                    feedback=feedback_items,
                    teacher_guidance_events=teacher_guidance_events,
                )

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

            current_candidate = self.revision_loop.revise(
                task=task,
                strategy=strategy,
                parent=current_candidate,
                feedback=feedback,
                revised_file_writes=revised_file_writes,
            )
            if teacher_guidance is not None:
                current_candidate.metadata["teacher_guidance"] = teacher_guidance
                current_candidate.metadata["teacher_trigger"] = teacher_result.routing_decision.trigger.value
                current_candidate.metadata["teacher_request_id"] = teacher_result.provider_response.request_id

        raise RuntimeError("iteration loop exited unexpectedly")
