from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas import TraceEvent, TraceEventType
from feiyue_core.schemas.common import FeiyueModel


class IterationResumeContext(FeiyueModel):
    session_id: str | None = None
    task_id: str | None = None
    latest_candidate_id: str | None = None
    parent_candidate_id: str | None = None
    latest_verification_result_id: str | None = None
    latest_feedback_category: str | None = None
    teacher_guidance_already_requested: bool = False
    completed: bool = False
    passed: bool = False
    next_safe_action: str
    candidate_lineage: list[str] = Field(default_factory=list)
    resume_summary: str


class IterationTraceReader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read_events(self) -> list[TraceEvent]:
        events: list[TraceEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                events.append(TraceEvent.model_validate(json.loads(stripped)))
        return events


class IterationResumeContextBuilder:
    def build(self, events: list[TraceEvent]) -> IterationResumeContext:
        session_id: str | None = None
        task_id: str | None = None
        latest_candidate_id: str | None = None
        parent_candidate_id: str | None = None
        latest_verification_result_id: str | None = None
        latest_feedback_category: str | None = None
        teacher_guidance_already_requested = False
        completed = False
        passed = False
        candidate_lineage: list[str] = []

        for event in events:
            session_id = session_id or event.session_id
            data = event.data
            if isinstance(data.get("task_id"), str):
                task_id = str(data["task_id"])

            if event.type == TraceEventType.CANDIDATE_GENERATED:
                candidate_id = data.get("candidate_id")
                if isinstance(candidate_id, str):
                    latest_candidate_id = candidate_id
                    candidate_lineage = [candidate_id]

            elif event.type == TraceEventType.CANDIDATE_REVISED:
                candidate_id = data.get("candidate_id")
                parent = data.get("parent_candidate_id")
                if isinstance(parent, str):
                    parent_candidate_id = parent
                    if parent not in candidate_lineage:
                        candidate_lineage.append(parent)
                if isinstance(candidate_id, str):
                    latest_candidate_id = candidate_id
                    if candidate_id not in candidate_lineage:
                        candidate_lineage.append(candidate_id)

            elif event.type in {TraceEventType.VERIFICATION_FAILED, TraceEventType.VERIFICATION_PASSED}:
                verification_id = data.get("verification_result_id")
                if isinstance(verification_id, str):
                    latest_verification_result_id = verification_id
                if event.type == TraceEventType.VERIFICATION_PASSED:
                    passed = True
                elif event.type == TraceEventType.VERIFICATION_FAILED:
                    passed = False

            elif event.type == TraceEventType.FEEDBACK_ANALYZED:
                feedback_category = data.get("feedback_category")
                if isinstance(feedback_category, str):
                    latest_feedback_category = feedback_category
                verification_id = data.get("verification_result_id")
                if isinstance(verification_id, str):
                    latest_verification_result_id = verification_id
                passed = bool(data.get("passed", passed))

            elif event.type == TraceEventType.TEACHER_GUIDANCE_REQUESTED:
                teacher_guidance_already_requested = True

            elif event.type == TraceEventType.ITERATION_COMPLETED:
                completed = True
                passed = bool(data.get("passed", passed))
                final_candidate = data.get("final_candidate_id")
                if isinstance(final_candidate, str):
                    latest_candidate_id = final_candidate

        next_safe_action = self._next_safe_action(
            completed=completed,
            passed=passed,
            latest_feedback_category=latest_feedback_category,
            teacher_guidance_already_requested=teacher_guidance_already_requested,
        )
        return IterationResumeContext(
            session_id=session_id,
            task_id=task_id,
            latest_candidate_id=latest_candidate_id,
            parent_candidate_id=parent_candidate_id,
            latest_verification_result_id=latest_verification_result_id,
            latest_feedback_category=latest_feedback_category,
            teacher_guidance_already_requested=teacher_guidance_already_requested,
            completed=completed,
            passed=passed,
            next_safe_action=next_safe_action,
            candidate_lineage=candidate_lineage,
            resume_summary=self._summary(
                task_id=task_id,
                latest_candidate_id=latest_candidate_id,
                candidate_lineage=candidate_lineage,
                latest_feedback_category=latest_feedback_category,
                latest_verification_result_id=latest_verification_result_id,
                teacher_guidance_already_requested=teacher_guidance_already_requested,
                completed=completed,
                passed=passed,
                next_safe_action=next_safe_action,
            ),
        )

    @staticmethod
    def _next_safe_action(
        *,
        completed: bool,
        passed: bool,
        latest_feedback_category: str | None,
        teacher_guidance_already_requested: bool,
    ) -> str:
        if completed and passed:
            return "promote verified candidate or run next acceptance gate"
        if completed and not passed:
            return "inspect failed final candidate before retrying"
        if latest_feedback_category and latest_feedback_category != "passed" and teacher_guidance_already_requested:
            return "revise latest candidate using existing teacher guidance; do not request duplicate teacher guidance"
        if latest_feedback_category and latest_feedback_category != "passed":
            return "request teacher guidance or revise latest candidate based on feedback"
        return "inspect trace and rebuild missing iteration state before continuing"

    @staticmethod
    def _summary(
        *,
        task_id: str | None,
        latest_candidate_id: str | None,
        candidate_lineage: list[str],
        latest_feedback_category: str | None,
        latest_verification_result_id: str | None,
        teacher_guidance_already_requested: bool,
        completed: bool,
        passed: bool,
        next_safe_action: str,
    ) -> str:
        lines = [
            f"task_id: {task_id or 'unknown'}",
            f"latest_candidate_id: {latest_candidate_id or 'unknown'}",
            f"latest_verification_result_id: {latest_verification_result_id or 'unknown'}",
            f"candidate_lineage: {' -> '.join(candidate_lineage) if candidate_lineage else 'unknown'}",
            f"completed: {completed}",
            f"passed: {passed}",
            f"next_safe_action: {next_safe_action}",
        ]
        if latest_feedback_category and latest_feedback_category != "passed" and not passed:
            lines.append(f"unresolved failure {latest_feedback_category}")
        if teacher_guidance_already_requested:
            lines.append("teacher guidance was already requested; do not request duplicate teacher guidance")
        return "\n".join(lines)
