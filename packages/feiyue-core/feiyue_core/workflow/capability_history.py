from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class CapabilityHistoryRecord(FeiyueModel):
    """One provider-free longitudinal capability observation from workflow evidence."""

    profile_id: str
    capability: str | None = None
    task_id: str | None = None
    run_id: str
    source_kind: str
    status: str
    verified: bool = False
    teacher_used: bool = False
    provider_call_count: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    promotion_attempted: bool = False
    promoted: bool = False
    source_evidence_path: str
    started_at: str | None = None
    completed_at: str | None = None
    written_at: str | None = None
    observed_at: str
    routing_table_mutated: bool = False


class CapabilityHistoryProfileSummary(FeiyueModel):
    profile_id: str
    total_runs: int = Field(default=0, ge=0)
    verified_runs: int = Field(default=0, ge=0)
    teacher_used_runs: int = Field(default=0, ge=0)
    provider_call_count: int = Field(default=0, ge=0)
    promotion_attempts: int = Field(default=0, ge=0)
    promoted_runs: int = Field(default=0, ge=0)
    capabilities: list[str] = Field(default_factory=list)


class CapabilityHistoryReport(FeiyueModel):
    generated_at: str
    total_records: int = Field(default=0, ge=0)
    records: list[CapabilityHistoryRecord]
    profile_summaries: dict[str, CapabilityHistoryProfileSummary]
    evidence_sources: list[str] = Field(default_factory=list)
    routing_table_mutated: bool = False

    def render_markdown(self) -> str:
        lines = [
            "# Capability History Report",
            "",
            f"- generated_at: {self.generated_at}",
            f"- total_records: {self.total_records}",
            f"- routing_table_mutated: {self.routing_table_mutated}",
            "",
            "## Profile Summaries",
        ]
        for profile_id in sorted(self.profile_summaries):
            summary = self.profile_summaries[profile_id]
            capabilities = ", ".join(summary.capabilities) if summary.capabilities else "none observed"
            lines.extend(
                [
                    f"### {profile_id}",
                    f"- total_runs: {summary.total_runs}",
                    f"- verified_runs: {summary.verified_runs}",
                    f"- teacher_used_runs: {summary.teacher_used_runs}",
                    f"- provider_call_count: {summary.provider_call_count}",
                    f"- promotion_attempts: {summary.promotion_attempts}",
                    f"- promoted_runs: {summary.promoted_runs}",
                    f"- capabilities: {capabilities}",
                    "",
                ]
            )
        lines.append("## Recent Records")
        for record in self.records:
            lines.append(
                "- "
                f"{record.run_id}: profile={record.profile_id}; task={record.task_id or 'unknown'}; "
                f"capability={record.capability or 'unknown'}; status={record.status}; "
                f"verified={record.verified}; teacher_used={record.teacher_used}; "
                f"promoted={record.promoted}; source={record.source_evidence_path}"
            )
        lines.append("")
        return "\n".join(lines)


class CapabilityHistoryCollector:
    """Collect workflow evidence into provider-free longitudinal capability history.

    This foundation is intentionally audit-only. It writes capability history
    artifacts under `.hermes/capability-history` and never mutates routing tables.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def build_report(self) -> CapabilityHistoryReport:
        generated_at = datetime.now(UTC).isoformat()
        promotions = self._load_promotion_records()
        records: list[CapabilityHistoryRecord] = []
        consumed_promotion_run_ids: set[str] = set()

        for path, payload in self._load_evidence_files("workflow-smokes", "evidence.json"):
            run_id = _string(payload.get("run_id")) or path.parent.name
            promotion = promotions.get(run_id)
            if promotion is not None:
                consumed_promotion_run_ids.add(run_id)
            records.append(
                self._record_from_payload(
                    payload,
                    path=path,
                    source_kind="workflow_smoke",
                    generated_at=generated_at,
                    promotion=promotion,
                )
            )

        for path, payload in self._load_evidence_files("multi-worker-workflows", "evidence.json"):
            run_id = _string(payload.get("run_id")) or path.parent.name
            promotion = promotions.get(run_id)
            if promotion is not None:
                consumed_promotion_run_ids.add(run_id)
            records.append(
                self._record_from_payload(
                    payload,
                    path=path,
                    source_kind="multi_worker_workflow",
                    generated_at=generated_at,
                    promotion=promotion,
                )
            )

        for run_id, promotion in sorted(promotions.items()):
            if run_id in consumed_promotion_run_ids:
                continue
            records.append(
                self._record_from_payload(
                    promotion["payload"],
                    path=promotion["path"],
                    source_kind="workflow_promotion",
                    generated_at=generated_at,
                    promotion=promotion,
                )
            )

        records.sort(key=lambda record: (record.observed_at, record.source_evidence_path, record.run_id))
        summaries = _summaries(records)
        return CapabilityHistoryReport(
            generated_at=generated_at,
            total_records=len(records),
            records=records,
            profile_summaries=summaries,
            evidence_sources=[record.source_evidence_path for record in records],
            routing_table_mutated=False,
        )

    def write_report(self) -> CapabilityHistoryReport:
        report = self.build_report()
        output_dir = self.project_root / ".hermes" / "capability-history"
        output_dir.mkdir(parents=True, exist_ok=True)
        history_lines = [record.model_dump_json() for record in report.records]
        (output_dir / "history.jsonl").write_text("\n".join(history_lines) + ("\n" if history_lines else ""), encoding="utf-8")
        (output_dir / "latest.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (output_dir / "latest.md").write_text(report.render_markdown(), encoding="utf-8")
        return report

    def _load_promotion_records(self) -> dict[str, dict[str, Any]]:
        promotions: dict[str, dict[str, Any]] = {}
        for path, payload in self._load_evidence_files("workflow-promotions", "promotion-evidence.json"):
            run_id = _string(payload.get("run_id")) or path.parent.name
            promotions[run_id] = {"path": path, "payload": payload}
        return promotions

    def _load_evidence_files(self, evidence_dir: str, filename: str) -> list[tuple[Path, dict[str, Any]]]:
        parent = self.project_root / ".hermes" / evidence_dir
        if not parent.exists():
            return []
        records: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(parent.glob(f"*/{filename}")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                records.append((path, payload))
        return records

    def _record_from_payload(
        self,
        payload: dict[str, Any],
        *,
        path: Path,
        source_kind: str,
        generated_at: str,
        promotion: dict[str, Any] | None,
    ) -> CapabilityHistoryRecord:
        workflow_report = _dict(payload.get("workflow_report"))
        dry_run_report = _dict(payload.get("dry_run_report"))
        promotion_payload = _dict(promotion.get("payload")) if promotion else {}
        status = _string(payload.get("status")) or _string(workflow_report.get("status")) or "unknown"
        verified = _bool(payload.get("verified")) or _bool(payload.get("verification_passed")) or status == "verified" or _bool(workflow_report.get("verification_passed"))
        teacher_events = workflow_report.get("teacher_guidance_events")
        teacher_used = bool(_string(payload.get("teacher_profile"))) or (isinstance(teacher_events, list) and len(teacher_events) > 0)
        promotion_attempted = _bool(payload.get("promotion_attempted")) or _bool(promotion_payload.get("promotion_attempted")) or bool(promotion_payload)
        promoted = _string(promotion_payload.get("status")) == "promoted" or _string(payload.get("status")) == "promoted"
        written_at = _first_string(payload.get("written_at"), workflow_report.get("written_at"), promotion_payload.get("written_at"))
        observed_at = _first_string(payload.get("completed_at"), workflow_report.get("completed_at"), written_at, generated_at) or generated_at
        return CapabilityHistoryRecord(
            profile_id=_first_string(payload.get("worker_profile"), payload.get("profile_id"), payload.get("profile")) or "unknown",
            capability=_first_string(payload.get("capability"), workflow_report.get("capability"), dry_run_report.get("capability")),
            task_id=_first_string(payload.get("task_id"), workflow_report.get("task_id"), promotion_payload.get("task_id")),
            run_id=_first_string(payload.get("run_id"), promotion_payload.get("run_id"), path.parent.name) or path.parent.name,
            source_kind=source_kind,
            status=status,
            verified=verified,
            teacher_used=teacher_used,
            provider_call_count=_coerce_int(payload.get("provider_call_count")),
            cost_usd=_coerce_float(payload.get("cost_usd"), payload.get("total_cost_usd"), workflow_report.get("cost_usd"), workflow_report.get("total_cost_usd")),
            latency_ms=_coerce_float(payload.get("latency_ms"), payload.get("duration_ms"), workflow_report.get("latency_ms"), workflow_report.get("duration_ms")),
            promotion_attempted=promotion_attempted,
            promoted=promoted,
            source_evidence_path=self._relative_source(path),
            started_at=_first_string(payload.get("started_at"), workflow_report.get("started_at")),
            completed_at=_first_string(payload.get("completed_at"), workflow_report.get("completed_at")),
            written_at=written_at,
            observed_at=observed_at,
            routing_table_mutated=False,
        )

    def _relative_source(self, path: Path) -> str:
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return path.as_posix()


def _summaries(records: list[CapabilityHistoryRecord]) -> dict[str, CapabilityHistoryProfileSummary]:
    mutable: dict[str, dict[str, Any]] = {}
    for record in records:
        bucket = mutable.setdefault(
            record.profile_id,
            {
                "profile_id": record.profile_id,
                "total_runs": 0,
                "verified_runs": 0,
                "teacher_used_runs": 0,
                "provider_call_count": 0,
                "promotion_attempts": 0,
                "promoted_runs": 0,
                "capabilities": set(),
            },
        )
        bucket["total_runs"] += 1
        bucket["verified_runs"] += 1 if record.verified else 0
        bucket["teacher_used_runs"] += 1 if record.teacher_used else 0
        bucket["provider_call_count"] += record.provider_call_count
        bucket["promotion_attempts"] += 1 if record.promotion_attempted else 0
        bucket["promoted_runs"] += 1 if record.promoted else 0
        if record.capability:
            bucket["capabilities"].add(record.capability)
    summaries: dict[str, CapabilityHistoryProfileSummary] = {}
    for profile_id, data in sorted(mutable.items()):
        capabilities = data["capabilities"]
        summaries[profile_id] = CapabilityHistoryProfileSummary(
            profile_id=str(data["profile_id"]),
            total_runs=int(data["total_runs"]),
            verified_runs=int(data["verified_runs"]),
            teacher_used_runs=int(data["teacher_used_runs"]),
            provider_call_count=int(data["provider_call_count"]),
            promotion_attempts=int(data["promotion_attempts"]),
            promoted_runs=int(data["promoted_runs"]),
            capabilities=sorted(capabilities) if isinstance(capabilities, set) else [],
        )
    return summaries


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_string(*values: object) -> str | None:
    for value in values:
        string = _string(value)
        if string is not None:
            return string
    return None


def _bool(value: object) -> bool:
    return value is True


def _coerce_int(value: object) -> int:
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return 0


def _coerce_float(*values: object) -> float | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and value >= 0:
            return float(value)
        if isinstance(value, str):
            try:
                parsed = float(value)
            except ValueError:
                continue
            if parsed >= 0:
                return parsed
    return None
