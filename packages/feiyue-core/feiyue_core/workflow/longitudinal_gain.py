from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class LongitudinalGainWindow(FeiyueModel):
    """Aggregate metrics for one chronological evaluation window."""

    sample_count: int = Field(default=0, ge=0)
    start_observed_at: str | None = None
    end_observed_at: str | None = None
    pass_rate: float | None = None
    teacher_call_rate: float | None = None
    average_cost_usd: float | None = None
    average_latency_ms: float | None = None


class LongitudinalGainGroup(FeiyueModel):
    """Before/after gain metrics for one profile/task/capability history group."""

    profile_id: str
    task_id: str
    capability: str
    total_samples: int = Field(default=0, ge=0)
    before: LongitudinalGainWindow
    after: LongitudinalGainWindow
    pass_rate_delta: float | None = None
    teacher_call_rate_delta: float | None = None
    cost_usd_delta: float | None = None
    latency_ms_delta: float | None = None
    confidence_label: str
    status: str
    insufficient_data_reason: str | None = None


class LongitudinalGainReport(FeiyueModel):
    """Provider-free longitudinal gain report derived from persisted evidence only."""

    generated_at: str
    history_path: str | None = None
    total_records: int = Field(default=0, ge=0)
    total_groups: int = Field(default=0, ge=0)
    min_samples: int = Field(default=3, ge=1)
    window_size: int = Field(default=3, ge=1)
    groups: list[LongitudinalGainGroup]
    routing_table_mutated: bool = False

    def render_markdown(self) -> str:
        lines = [
            "# Longitudinal Gain Report",
            "",
            f"- generated_at: {self.generated_at}",
            f"- history_path: {self.history_path or 'in-memory'}",
            f"- total_records: {self.total_records}",
            f"- total_groups: {self.total_groups}",
            f"- min_samples: {self.min_samples}",
            f"- window_size: {self.window_size}",
            f"- routing_table_mutated: {self.routing_table_mutated}",
            "",
            "## Groups",
        ]
        if not self.groups:
            lines.append("- none")
        for group in self.groups:
            lines.extend(
                [
                    f"### {group.profile_id} / {group.task_id} / {group.capability}",
                    f"- status: {group.status}",
                    f"- confidence_label: {group.confidence_label}",
                    f"- total_samples: {group.total_samples}",
                    f"- before_samples: {group.before.sample_count}",
                    f"- after_samples: {group.after.sample_count}",
                    f"- pass_rate_delta: {_format_optional(group.pass_rate_delta)}",
                    f"- teacher_call_rate_delta: {_format_optional(group.teacher_call_rate_delta)}",
                    f"- cost_usd_delta: {_format_optional(group.cost_usd_delta)}",
                    f"- latency_ms_delta: {_format_optional(group.latency_ms_delta)}",
                ]
            )
            if group.insufficient_data_reason:
                lines.append(f"- insufficient_data_reason: {group.insufficient_data_reason}")
            lines.append("")
        return "\n".join(lines)


class LongitudinalGainEvaluator:
    """Evaluate gains over capability-history records without providers or routing mutations."""

    def __init__(
        self,
        records: Iterable[dict[str, Any]],
        *,
        history_path: str | Path | None = None,
        min_samples: int = 3,
        window_size: int = 3,
    ) -> None:
        if min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self.records = [dict(record) for record in records]
        self.history_path = Path(history_path) if history_path is not None else None
        self.min_samples = min_samples
        self.window_size = window_size

    @classmethod
    def from_history_path(
        cls,
        history_path: str | Path,
        *,
        min_samples: int = 3,
        window_size: int = 3,
    ) -> "LongitudinalGainEvaluator":
        path = Path(history_path)
        records: list[dict[str, Any]] = []
        if path.exists():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    raise ValueError(f"history line {line_number} is not a JSON object")
                records.append(payload)
        return cls(records, history_path=path, min_samples=min_samples, window_size=window_size)

    def build_report(self) -> LongitudinalGainReport:
        generated_at = datetime.now(UTC).isoformat()
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for record in self.records:
            key = (_text(record.get("profile_id"), "unknown"), _text(record.get("task_id"), "unknown"), _text(record.get("capability"), "unknown"))
            grouped.setdefault(key, []).append(record)

        groups: list[LongitudinalGainGroup] = []
        for (profile_id, task_id, capability), records in sorted(grouped.items()):
            sorted_records = sorted(records, key=_record_sort_key)
            groups.append(self._build_group(profile_id, task_id, capability, sorted_records))

        return LongitudinalGainReport(
            generated_at=generated_at,
            history_path=self.history_path.as_posix() if self.history_path is not None else None,
            total_records=len(self.records),
            total_groups=len(groups),
            min_samples=self.min_samples,
            window_size=self.window_size,
            groups=groups,
            routing_table_mutated=False,
        )

    def write_report(self, project_root: str | Path) -> LongitudinalGainReport:
        report = self.build_report()
        output_dir = Path(project_root) / ".hermes" / "longitudinal-gain"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "latest.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (output_dir / "latest.md").write_text(report.render_markdown(), encoding="utf-8")
        return report

    def _build_group(self, profile_id: str, task_id: str, capability: str, records: list[dict[str, Any]]) -> LongitudinalGainGroup:
        required_total = self.min_samples * 2
        if len(records) < required_total:
            reason = f"requires at least {required_total} samples ({self.min_samples} before and {self.min_samples} after); found {len(records)}"
            return LongitudinalGainGroup(
                profile_id=profile_id,
                task_id=task_id,
                capability=capability,
                total_samples=len(records),
                before=LongitudinalGainWindow(),
                after=LongitudinalGainWindow(),
                confidence_label="insufficient_data",
                status="insufficient_data",
                insufficient_data_reason=reason,
            )

        before_records = records[: self.window_size]
        after_records = records[-self.window_size :]
        if len(before_records) < self.min_samples or len(after_records) < self.min_samples:
            reason = f"before/after windows must each contain at least {self.min_samples} samples"
            return LongitudinalGainGroup(
                profile_id=profile_id,
                task_id=task_id,
                capability=capability,
                total_samples=len(records),
                before=LongitudinalGainWindow(),
                after=LongitudinalGainWindow(),
                confidence_label="insufficient_data",
                status="insufficient_data",
                insufficient_data_reason=reason,
            )

        before = _window(before_records)
        after = _window(after_records)
        return LongitudinalGainGroup(
            profile_id=profile_id,
            task_id=task_id,
            capability=capability,
            total_samples=len(records),
            before=before,
            after=after,
            pass_rate_delta=_delta(after.pass_rate, before.pass_rate),
            teacher_call_rate_delta=_delta(after.teacher_call_rate, before.teacher_call_rate),
            cost_usd_delta=_delta(after.average_cost_usd, before.average_cost_usd),
            latency_ms_delta=_delta(after.average_latency_ms, before.average_latency_ms),
            confidence_label=_confidence_label(before.sample_count, after.sample_count),
            status="evaluated",
        )


def build_longitudinal_gain_report_from_history(
    history_path: str | Path,
    *,
    min_samples: int = 3,
    window_size: int = 3,
) -> LongitudinalGainReport:
    return LongitudinalGainEvaluator.from_history_path(history_path, min_samples=min_samples, window_size=window_size).build_report()


def _window(records: list[dict[str, Any]]) -> LongitudinalGainWindow:
    costs = [_number_from(record, "cost_usd", "total_cost_usd", "cost") for record in records]
    latencies = [_number_from(record, "latency_ms", "duration_ms", "elapsed_ms") for record in records]
    observed = [_text(record.get("observed_at"), "") for record in records]
    return LongitudinalGainWindow(
        sample_count=len(records),
        start_observed_at=observed[0] or None,
        end_observed_at=observed[-1] or None,
        pass_rate=_round(sum(1 for record in records if _passed(record)) / len(records)),
        teacher_call_rate=_round(sum(1 for record in records if record.get("teacher_used") is True) / len(records)),
        average_cost_usd=_average([value for value in costs if value is not None]),
        average_latency_ms=_average([value for value in latencies if value is not None]),
    )


def _passed(record: dict[str, Any]) -> bool:
    if record.get("verified") is True:
        return True
    status = _text(record.get("status"), "").lower()
    return status in {"verified", "promoted", "succeeded", "success", "passed", "pass"}


def _number_from(record: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return _round(sum(values) / len(values))


def _delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return _round(after - before)


def _round(value: float) -> float:
    rounded = round(value, 6)
    if rounded == 0:
        return 0.0
    return rounded


def _confidence_label(before_count: int, after_count: int) -> str:
    minimum = min(before_count, after_count)
    if minimum >= 30:
        return "high"
    if minimum >= 10:
        return "medium"
    return "low"


def _record_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    observed_at = _text(record.get("observed_at"), "")
    run_id = _text(record.get("run_id"), "")
    return observed_at, run_id


def _text(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _format_optional(value: float | None) -> str:
    return "n/a" if value is None else str(value)
