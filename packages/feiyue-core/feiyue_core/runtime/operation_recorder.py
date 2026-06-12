from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from feiyue_core.recovery import OperationRecord, OperationRiskLevel, OperationStatus, RecoveryManifest
from feiyue_core.schemas import TraceEvent, TraceEventType

from .journal import SessionJournal


class OperationRecorder:
    def __init__(self, journal: SessionJournal) -> None:
        self.journal = journal
        self._records: dict[str, OperationRecord] = {}

    def register(
        self,
        operation_id: str,
        tool: str,
        args: dict[str, object],
        risk_level: OperationRiskLevel,
        preconditions: dict[str, object],
        side_effect_checks: list[dict[str, object]] | None = None,
    ) -> OperationRecord:
        record = OperationRecord(
            operation_id=operation_id,
            tool=tool,
            args_hash=self._hash_args(args),
            status=OperationStatus.STARTED,
            risk_level=risk_level,
            preconditions=preconditions,
        )
        self._records[operation_id] = record
        manifest = self._read_or_create_manifest()
        if operation_id not in manifest.pending_operations:
            manifest.pending_operations.append(operation_id)
        manifest.operation_risk_levels[operation_id] = risk_level.value
        checks = side_effect_checks or self._derive_side_effect_checks(tool, args)
        if checks:
            manifest.side_effect_checks[operation_id] = checks
        self.journal.write_manifest(manifest)
        self._append_event(
            TraceEventType.TOOL_OPERATION_STARTED,
            f"operation {operation_id} started",
            {"operation_id": operation_id, "tool": tool, "risk_level": risk_level.value},
        )
        return record

    def finish(
        self,
        operation_id: str,
        postconditions: dict[str, object],
        artifact_refs: list[str] | None = None,
    ) -> OperationRecord:
        record = self._require_record(operation_id)
        record.status = OperationStatus.FINISHED
        record.postconditions = postconditions
        record.artifact_refs = artifact_refs or []
        manifest = self._read_or_create_manifest()
        manifest.pending_operations = [op for op in manifest.pending_operations if op != operation_id]
        manifest.operation_risk_levels.pop(operation_id, None)
        manifest.side_effect_checks.pop(operation_id, None)
        output = f"operation {operation_id} finished"
        if output not in manifest.verified_outputs:
            manifest.verified_outputs.append(output)
        self.journal.write_manifest(manifest)
        self._append_event(
            TraceEventType.TOOL_OPERATION_FINISHED,
            output,
            {"operation_id": operation_id, "artifact_refs": record.artifact_refs},
        )
        return record

    def mark_unknown(self, operation_id: str, reason: str) -> OperationRecord:
        record = self._require_record(operation_id)
        record.status = OperationStatus.UNKNOWN
        manifest = self._read_or_create_manifest()
        if operation_id not in manifest.pending_operations:
            manifest.pending_operations.append(operation_id)
        question = f"operation {operation_id} unknown: {reason}"
        if question not in manifest.open_questions:
            manifest.open_questions.append(question)
        self.journal.write_manifest(manifest)
        self._append_event(
            TraceEventType.TOOL_OPERATION_UNKNOWN,
            question,
            {"operation_id": operation_id, "reason": reason},
        )
        return record

    def _require_record(self, operation_id: str) -> OperationRecord:
        if operation_id not in self._records:
            raise KeyError(f"operation not registered: {operation_id}")
        return self._records[operation_id]

    def _read_or_create_manifest(self) -> RecoveryManifest:
        if self.journal.manifest_path.exists():
            return self.journal.read_manifest()
        return RecoveryManifest(session_id="unknown", current_goal="unknown")

    def _append_event(self, event_type: TraceEventType, message: str, data: dict[str, object]) -> None:
        self.journal.append(
            TraceEvent(
                id=f"evt_{uuid4().hex}",
                session_id=self._read_or_create_manifest().session_id,
                type=event_type,
                message=message,
                data=data,
            )
        )

    @staticmethod
    def _hash_args(args: dict[str, object]) -> str:
        encoded = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _derive_side_effect_checks(tool: str, args: dict[str, object]) -> list[dict[str, object]]:
        checks: list[dict[str, object]] = []
        if tool == "write_file":
            path = args.get("path")
            content = args.get("content")
            if isinstance(path, str) and content is not None:
                encoded = str(content).encode("utf-8")
                checks.append(
                    {
                        "type": "file_hash",
                        "path": path,
                        "expected_sha256": hashlib.sha256(encoded).hexdigest(),
                    }
                )

        repo_path = args.get("repo_path")
        ref = args.get("ref") or args.get("remote_ref")
        expected_sha = args.get("expected_sha")
        has_git_ref_contract = all(isinstance(value, str) for value in [repo_path, ref, expected_sha])
        if tool in {"git_push", "git_update_ref"} and has_git_ref_contract:
            checks.append(
                {
                    "type": "git_ref",
                    "repo_path": repo_path,
                    "ref": ref,
                    "expected_sha": expected_sha,
                }
            )

        artifact_path = args.get("artifact_path")
        if isinstance(artifact_path, str):
            checks.append({"type": "artifact_exists", "path": artifact_path})
        artifact_paths = args.get("artifact_paths")
        if isinstance(artifact_paths, list):
            for path in artifact_paths:
                if isinstance(path, str):
                    checks.append({"type": "artifact_exists", "path": path})
        return checks
