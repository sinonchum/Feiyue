from __future__ import annotations

import hashlib
import json

from feiyue_core.schemas import Candidate, CandidateStatus, StrategyVersion, TaskSpec


class CandidateGenerator:
    def generate(
        self,
        task: TaskSpec,
        strategy: StrategyVersion,
        file_writes: dict[str, str],
    ) -> Candidate:
        normalized_writes = dict(sorted(file_writes.items()))
        candidate_id = self._candidate_id(task.id, strategy.id, normalized_writes)
        touched = ", ".join(normalized_writes.keys()) or "no files"
        return Candidate(
            id=candidate_id,
            task_id=task.id,
            status=CandidateStatus.GENERATED,
            strategy_version_id=strategy.id,
            summary=f"{strategy.name} candidate for {task.id} touching {touched}",
            metadata={
                "file_writes": normalized_writes,
                "acceptance_criteria": task.acceptance_criteria,
                "target_files": task.metadata.get("target_files", []),
            },
        )

    @staticmethod
    def _candidate_id(task_id: str, strategy_id: str, file_writes: dict[str, str]) -> str:
        payload = json.dumps(
            {"task_id": task_id, "strategy_id": strategy_id, "file_writes": file_writes},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"cand_{hashlib.sha256(payload).hexdigest()[:16]}"
