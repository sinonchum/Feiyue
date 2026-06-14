from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.live_smoke_plan import (
    LiveSmokeAuthorization,
    LiveSmokePlanStatus,
    LiveSmokeTeacherEscalationAuthorization,
    build_live_smoke_plan,
    live_smoke_approval_path,
    live_smoke_plan_path,
    live_smoke_teacher_approval_path,
    write_live_smoke_plan,
)


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = f"{source_path}{os.pathsep}{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else source_path
    return env


def _approval(plan_id: str = "batch1-live-ab") -> LiveSmokeAuthorization:
    return LiveSmokeAuthorization(
        authorization_id="auth.batch1.live-ab",
        authorized_by="test-suite",
        plan_id=plan_id,
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        approved_action="prepare_live_ab_smoke_dry_run",
        worker_profile_id="worker-a",
        scopes=["live_smoke_prepare"],
        max_profile_calls=1,
        timeout_seconds=120,
        budget_ceiling="0.01 USD",
        dry_run_only=True,
        promotion_disabled=True,
        reason="Approve plan-only live A/B dry-run smoke preparation.",
    )


def _teacher_approval(plan_id: str = "batch1-live-ab") -> LiveSmokeTeacherEscalationAuthorization:
    return LiveSmokeTeacherEscalationAuthorization(
        authorization_id="auth.batch1.live-ab.teacher",
        authorized_by="test-suite",
        plan_id=plan_id,
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        approved_action="prepare_live_ab_teacher_escalation_dry_run",
        worker_profile_id="worker-a",
        teacher_profile_id="teacher-a",
        scopes=["live_smoke_teacher_escalation"],
        max_profile_calls=3,
        timeout_seconds=180,
        budget_ceiling="0.03 USD",
        dry_run_only=True,
        promotion_disabled=True,
        reason="Approve plan-only teacher escalation smoke preparation.",
    )


def test_missing_approvals_are_blocked_fail_closed(tmp_path: Path) -> None:
    plan = build_live_smoke_plan(
        project_root=tmp_path,
        plan_id="batch1-live-ab",
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        worker_profile_id="worker-a",
        expected_verifier_command="python -m pytest -q packages/feiyue-core/tests/test_live_smoke_plan.py",
    )

    assert plan.status == LiveSmokePlanStatus.BLOCKED
    assert plan.ready is False
    assert "missing_live_smoke_approval" in plan.reason_codes
    assert plan.dry_run_only is True
    assert plan.promotion_disabled is True
    assert plan.global_hermes_config_mutated is False
    assert plan.production_side_effects_enabled is False
    assert plan.provider_call_count == 0
    assert plan.required_approval_paths == [str(live_smoke_approval_path(tmp_path, "batch1-live-ab"))]


def test_exact_approval_marks_plan_ready_without_execution(tmp_path: Path) -> None:
    approval_path = live_smoke_approval_path(tmp_path, "batch1-live-ab")
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(_approval().model_dump_json(indent=2), encoding="utf-8")

    plan = build_live_smoke_plan(
        project_root=tmp_path,
        plan_id="batch1-live-ab",
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        worker_profile_id="worker-a",
        expected_verifier_command="python -m pytest -q packages/feiyue-core/tests/test_live_smoke_plan.py",
        max_profile_calls=1,
        timeout_seconds=120,
        budget_ceiling="0.01 USD",
    )

    assert plan.status == LiveSmokePlanStatus.READY
    assert plan.ready is True
    assert plan.authorization_id == "auth.batch1.live-ab"
    assert plan.selected_worker_profile == "worker-a"
    assert plan.optional_teacher_profile is None
    assert plan.reason_codes == ["live_smoke_approval_applies", "plan_only_no_live_calls"]
    assert plan.provider_call_count == 0
    assert plan.expected_verifier_command.startswith("python -m pytest")
    assert plan.required_evidence_paths == [str(tmp_path / ".hermes" / "live-smokes" / "run.batch1.live-ab" / "evidence.json")]


def test_mismatched_approval_is_blocked(tmp_path: Path) -> None:
    approval_path = live_smoke_approval_path(tmp_path, "batch1-live-ab")
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(_approval(plan_id="other-plan").model_dump_json(indent=2), encoding="utf-8")

    plan = build_live_smoke_plan(
        project_root=tmp_path,
        plan_id="batch1-live-ab",
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        worker_profile_id="worker-a",
        expected_verifier_command="python -m pytest -q",
    )

    assert plan.status == LiveSmokePlanStatus.BLOCKED
    assert "approval_plan_id_mismatch" in plan.reason_codes


def test_teacher_escalation_requires_separate_authorization_if_enabled(tmp_path: Path) -> None:
    approval_path = live_smoke_approval_path(tmp_path, "batch1-live-ab")
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(_approval().model_dump_json(indent=2), encoding="utf-8")

    plan = build_live_smoke_plan(
        project_root=tmp_path,
        plan_id="batch1-live-ab",
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        worker_profile_id="worker-a",
        teacher_profile_id="teacher-a",
        teacher_escalation_enabled=True,
        expected_verifier_command="python -m pytest -q",
    )

    assert plan.status == LiveSmokePlanStatus.BLOCKED
    assert plan.optional_teacher_profile == "teacher-a"
    assert "missing_live_smoke_teacher_escalation_approval" in plan.reason_codes
    assert str(live_smoke_teacher_approval_path(tmp_path, "batch1-live-ab")) in plan.required_approval_paths


def test_teacher_escalation_separate_authorization_marks_ready(tmp_path: Path) -> None:
    approval_path = live_smoke_approval_path(tmp_path, "batch1-live-ab")
    teacher_path = live_smoke_teacher_approval_path(tmp_path, "batch1-live-ab")
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(_approval().model_dump_json(indent=2), encoding="utf-8")
    teacher_path.write_text(_teacher_approval().model_dump_json(indent=2), encoding="utf-8")

    plan = build_live_smoke_plan(
        project_root=tmp_path,
        plan_id="batch1-live-ab",
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        worker_profile_id="worker-a",
        teacher_profile_id="teacher-a",
        teacher_escalation_enabled=True,
        expected_verifier_command="python -m pytest -q",
    )

    assert plan.status == LiveSmokePlanStatus.READY
    assert plan.teacher_authorization_id == "auth.batch1.live-ab.teacher"
    assert "live_smoke_teacher_escalation_approval_applies" in plan.reason_codes


def test_write_plan_persists_json_and_markdown_without_global_mutation(tmp_path: Path) -> None:
    approval_path = live_smoke_approval_path(tmp_path, "batch1-live-ab")
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(_approval().model_dump_json(indent=2), encoding="utf-8")

    plan = write_live_smoke_plan(
        project_root=tmp_path,
        plan_id="batch1-live-ab",
        run_id="run.batch1.live-ab",
        task_id="task.batch1.live-ab",
        worker_profile_id="worker-a",
        expected_verifier_command="python -m pytest -q",
    )

    path = live_smoke_plan_path(tmp_path, "batch1-live-ab")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["global_hermes_config_mutated"] is False
    assert payload["production_side_effects_enabled"] is False
    assert payload["promotion_disabled"] is True
    assert plan.provider_call_count == 0
    assert (path.parent / "plan.md").exists()


def test_cli_writes_live_smoke_plan_without_live_calls(tmp_path: Path) -> None:
    approval_path = live_smoke_approval_path(tmp_path, "batch1-live-ab")
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(_approval().model_dump_json(indent=2), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "live-smoke-plan",
            "--plan-id",
            "batch1-live-ab",
            "--run-id",
            "run.batch1.live-ab",
            "--task-id",
            "task.batch1.live-ab",
            "--worker-profile",
            "worker-a",
            "--expected-verifier-command",
            "python -m pytest -q",
            "--write-plan",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "ready"
    assert payload["provider_call_count"] == 0
    assert payload["production_side_effects_enabled"] is False
    assert live_smoke_plan_path(tmp_path, "batch1-live-ab").exists()
