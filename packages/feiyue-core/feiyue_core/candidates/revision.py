from __future__ import annotations

import hashlib
import json

from feiyue_core.schemas import Candidate, CandidateStatus, StrategyVersion, TaskSpec

from .feedback import VerificationFeedback


class CandidateRevisionLoop:
    def revise(
        self,
        task: TaskSpec,
        strategy: StrategyVersion,
        parent: Candidate,
        feedback: VerificationFeedback,
        revised_file_writes: dict[str, str],
    ) -> Candidate:
        normalized_writes = dict(sorted(revised_file_writes.items()))
        revision_index = int(parent.metadata.get("revision_index", 0)) + 1
        return Candidate(
            id=self._revision_id(task.id, strategy.id, parent.id, feedback, normalized_writes, revision_index),
            task_id=task.id,
            status=CandidateStatus.GENERATED,
            strategy_version_id=strategy.id,
            summary=f"{strategy.name} revision for {task.id} after {feedback.category}",
            metadata={
                "file_writes": normalized_writes,
                "acceptance_criteria": task.acceptance_criteria,
                "target_files": task.metadata.get("target_files", []),
                "parent_candidate_id": parent.id,
                "revision_reason": feedback.summary,
                "feedback_category": feedback.category,
                "feedback_evidence_excerpt": feedback.evidence_excerpt,
                "revision_index": revision_index,
            },
        )

    @staticmethod
    def _revision_id(
        task_id: str,
        strategy_id: str,
        parent_candidate_id: str,
        feedback: VerificationFeedback,
        file_writes: dict[str, str],
        revision_index: int,
    ) -> str:
        payload = json.dumps(
            {
                "task_id": task_id,
                "strategy_id": strategy_id,
                "parent_candidate_id": parent_candidate_id,
                "feedback_result_id": feedback.verification_result_id,
                "file_writes": file_writes,
                "revision_index": revision_index,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"cand_rev_{hashlib.sha256(payload).hexdigest()[:16]}"
