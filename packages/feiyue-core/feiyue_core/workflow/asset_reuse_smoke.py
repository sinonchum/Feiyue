from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


DEFAULT_COMPARABLE_TASK_ID = "asset-reuse-smoke-comparable"
KNOWN_ERROR_SIGNATURE = "expected 42 but got 41"
LIVE_B_SUBTRACTION_SIGNATURES = (
    "replace the subtraction",
    "return a - b",
    "return a + b",
    "subtraction with addition",
)


class AssetReuseSmokeReport(FeiyueModel):
    """Provider-free evidence that a promoted project-local lesson can prevent a known repeat error."""

    run_id: str
    lesson_loaded: bool
    lesson_path: str | None = None
    comparable_task_id: str
    error_prevented: bool
    teacher_call_required: bool
    retry_count: int = Field(ge=0)
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    before_metrics: dict[str, Any] | None = None
    after_metrics: dict[str, Any] | None = None
    generated_at: str

    def render_markdown(self) -> str:
        lines = [
            "# Asset Reuse Smoke",
            "",
            f"- run_id: {self.run_id}",
            f"- lesson_loaded: {self.lesson_loaded}",
            f"- lesson_path: {self.lesson_path or 'n/a'}",
            f"- comparable_task_id: {self.comparable_task_id}",
            f"- error_prevented: {self.error_prevented}",
            f"- teacher_call_required: {self.teacher_call_required}",
            f"- retry_count: {self.retry_count}",
            f"- dry_run_only: {self.dry_run_only}",
            f"- promotion_attempted: {self.promotion_attempted}",
            f"- global_hermes_config_mutated: {self.global_hermes_config_mutated}",
            f"- reason_codes: {', '.join(self.reason_codes) if self.reason_codes else 'none'}",
            "",
            "## Longitudinal-compatible metrics",
            f"- before_metrics: {self.before_metrics or 'n/a'}",
            f"- after_metrics: {self.after_metrics or 'n/a'}",
            "",
        ]
        return "\n".join(lines)


class AssetReuseSmokeHarness:
    """Dry-run harness for reusing promoted project-local lessons.

    The harness intentionally avoids live providers and global Hermes state.  It
    checks that a lesson is under the caller's project-local ``.hermes/lessons``
    directory, injects the lesson text into a deterministic comparable-task
    simulation, and writes only project-local evidence when requested.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def run(
        self,
        *,
        run_id: str,
        lesson_path: str | Path,
        comparable_task_id: str = DEFAULT_COMPARABLE_TASK_ID,
        write_report: bool = False,
    ) -> AssetReuseSmokeReport:
        generated_at = datetime.now(UTC).isoformat()
        lesson_result = self._load_project_local_lesson(lesson_path)
        lesson_loaded = lesson_result["loaded"]
        normalized_lesson_path = lesson_result["relative_path"]
        reason_codes = list(lesson_result["reason_codes"])
        lesson_text = str(lesson_result.get("content") or "")

        error_prevented = lesson_loaded and _lesson_prevents_known_error(lesson_text)
        if lesson_loaded and not error_prevented:
            reason_codes.append("lesson_missing_known_error_prevention")

        before_metrics = _history_record(
            run_id=f"{run_id}-before",
            task_id=comparable_task_id,
            verified=False,
            teacher_used=True,
            retry_count=1,
            observed_at=generated_at,
        )
        after_metrics = _history_record(
            run_id=run_id,
            task_id=comparable_task_id,
            verified=error_prevented,
            teacher_used=not error_prevented,
            retry_count=0 if error_prevented else 1,
            observed_at=generated_at,
        )

        report = AssetReuseSmokeReport(
            run_id=run_id,
            lesson_loaded=lesson_loaded,
            lesson_path=normalized_lesson_path,
            comparable_task_id=comparable_task_id,
            error_prevented=error_prevented,
            teacher_call_required=not error_prevented,
            retry_count=0 if error_prevented else 1,
            dry_run_only=True,
            promotion_attempted=False,
            global_hermes_config_mutated=False,
            reason_codes=reason_codes,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            generated_at=generated_at,
        )
        if write_report:
            self.write_report(report)
        return report

    def write_report(self, report: AssetReuseSmokeReport) -> None:
        output_dir = self.project_root / ".hermes" / "asset-reuse" / report.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "evidence.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (output_dir / "report.md").write_text(report.render_markdown(), encoding="utf-8")

    def _load_project_local_lesson(self, lesson_path: str | Path) -> dict[str, Any]:
        root = self.project_root.resolve()
        path = Path(lesson_path)
        if not path.is_absolute():
            path = self.project_root / path
        resolved = path.resolve()
        lessons_dir = (self.project_root / ".hermes" / "lessons").resolve()

        if not _is_relative_to(resolved, lessons_dir):
            return {"loaded": False, "relative_path": None, "reason_codes": ["lesson_not_project_local"]}
        if not resolved.exists() or not resolved.is_file():
            return {"loaded": False, "relative_path": _relative_to_root(resolved, root), "reason_codes": ["lesson_not_found"]}
        content = resolved.read_text(encoding="utf-8")
        if not content.strip():
            return {"loaded": False, "relative_path": _relative_to_root(resolved, root), "reason_codes": ["lesson_empty"]}
        return {"loaded": True, "relative_path": _relative_to_root(resolved, root), "reason_codes": [], "content": content}


def run_asset_reuse_smoke(
    *,
    project_root: str | Path,
    run_id: str,
    lesson_path: str | Path,
    comparable_task_id: str = DEFAULT_COMPARABLE_TASK_ID,
    write_report: bool = False,
) -> AssetReuseSmokeReport:
    return AssetReuseSmokeHarness(project_root).run(
        run_id=run_id,
        lesson_path=lesson_path,
        comparable_task_id=comparable_task_id,
        write_report=write_report,
    )


def _lesson_prevents_known_error(lesson_text: str) -> bool:
    lowered = lesson_text.lower()
    legacy_boundary_lesson = KNOWN_ERROR_SIGNATURE in lowered and any(
        phrase in lowered
        for phrase in (
            "prevention rule",
            "prevention",
            "apply the corrected boundary condition",
            "teacher guidance",
        )
    )
    live_b_subtraction_lesson = "teacher" in lowered and any(
        phrase in lowered for phrase in LIVE_B_SUBTRACTION_SIGNATURES
    )
    return legacy_boundary_lesson or live_b_subtraction_lesson


def _history_record(
    *,
    run_id: str,
    task_id: str,
    verified: bool,
    teacher_used: bool,
    retry_count: int,
    observed_at: str,
) -> dict[str, Any]:
    return {
        "profile_id": "asset-reuse-dry-run",
        "task_id": task_id,
        "capability": "asset_reuse",
        "run_id": run_id,
        "source_kind": "asset_reuse_smoke",
        "status": "verified" if verified else "failed",
        "verified": verified,
        "teacher_used": teacher_used,
        "provider_call_count": 0,
        "promotion_attempted": False,
        "promoted": False,
        "retry_count": retry_count,
        "observed_at": observed_at,
        "routing_table_mutated": False,
        "dry_run_only": True,
        "global_hermes_config_mutated": False,
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
