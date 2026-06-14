from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from feiyue_core.schemas.common import FeiyueModel

Wave9AssignmentRole = Literal["implementation", "tests", "docs", "review", "verifier"]
Wave9MergeStrategy = Literal["reject_on_conflict", "ordered_overlay", "reviewer_selected_patch"]


class Wave9TaskAssignment(FeiyueModel):
    assignment_id: str
    profile_id: str
    role: Wave9AssignmentRole
    objective: str
    allowed_files: list[str]
    verifier_commands: list[str]
    max_profile_calls: int = Field(default=1, ge=1)
    depends_on_assignment_ids: list[str] = Field(default_factory=list)

    @field_validator("assignment_id", "profile_id", "role", "objective")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("assignment fields must be non-empty")
        return normalized

    @field_validator("allowed_files", "verifier_commands")
    @classmethod
    def _required_string_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("allowed_files and verifier_commands must contain non-empty strings")
        return normalized


class Wave9TaskPack(FeiyueModel):
    task_pack_id: str
    task_id: str
    title: str
    summary: str
    assignments: list[Wave9TaskAssignment]
    merge_strategy: Wave9MergeStrategy = "reject_on_conflict"
    verifier_commands: list[str]
    review_criteria: list[str]
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    provider_call_count: int = 0
    reason_codes: list[str]
    task_pack_hash: str | None = None

    @field_validator("task_pack_id", "task_id", "title", "summary")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("task pack fields must be non-empty")
        return normalized

    @field_validator("verifier_commands", "review_criteria", "reason_codes")
    @classmethod
    def _required_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("task pack lists must contain non-empty strings")
        return normalized

    @field_validator("assignments")
    @classmethod
    def _at_least_two_assignments(cls, value: list[Wave9TaskAssignment]) -> list[Wave9TaskAssignment]:
        if len(value) < 2:
            raise ValueError("Wave9 task packs require at least two assignments")
        assignment_ids = [assignment.assignment_id for assignment in value]
        if len(set(assignment_ids)) != len(assignment_ids):
            raise ValueError("assignment_id values must be unique")
        return value

    @model_validator(mode="after")
    def _safe_pre_execution_contract(self) -> "Wave9TaskPack":
        if self.dry_run_only is not True:
            raise ValueError("Wave9 task packs must be dry_run_only")
        if self.promotion_attempted is not False:
            raise ValueError("Wave9 task packs cannot attempt promotion")
        if self.global_hermes_config_mutated is not False:
            raise ValueError("Wave9 task packs cannot mutate global Hermes config")
        if self.production_mutated is not False:
            raise ValueError("Wave9 task packs cannot mutate production")
        if self.provider_call_count != 0:
            raise ValueError("Wave9 task packs are pre-execution and must have provider_call_count 0")
        seen: set[str] = set()
        overlaps: set[str] = set()
        for assignment in self.assignments:
            for file_path in assignment.allowed_files:
                if file_path in seen:
                    overlaps.add(file_path)
                seen.add(file_path)
        if overlaps and self.merge_strategy != "reject_on_conflict":
            raise ValueError("overlapping assignment scopes require reject_on_conflict")
        return self


def task_pack_hash(pack: Wave9TaskPack) -> str:
    payload = pack.model_dump(mode="json")
    payload["task_pack_hash"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wave9_task_pack_path(project_root: str | Path, task_pack_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-task-packs" / task_pack_id / "task-pack.json"


def write_wave9_task_pack(pack: Wave9TaskPack, project_root: str | Path) -> Path:
    pack_with_hash = pack.model_copy(update={"task_pack_hash": task_pack_hash(pack)})
    path = wave9_task_pack_path(project_root, pack.task_pack_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack_with_hash.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_wave9_task_pack(project_root: str | Path, task_pack_id: str) -> Wave9TaskPack:
    path = wave9_task_pack_path(project_root, task_pack_id)
    return Wave9TaskPack.model_validate_json(path.read_text(encoding="utf-8"))
