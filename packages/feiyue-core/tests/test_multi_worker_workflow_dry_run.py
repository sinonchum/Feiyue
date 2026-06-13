from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from feiyue_core.providers.profile_runner import FakeProfileRunner, ProfileRunRequest, ProfileRunResult
from feiyue_core.workflow.model_routing_table import ModelRoutingTable, ModelRoutingTableInitializer
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlanner
from feiyue_core.workflow.multi_worker_workflow_dry_run import (
    MultiWorkerWorkflowDryRunAuthorization,
    MultiWorkerWorkflowDryRunOrchestrator,
    MultiWorkerWorkflowDryRunStatus,
)
from feiyue_core.workflow.task_contract import TaskContract


def _init_toy_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, text=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, text=True, capture_output=True)


def _write_routing(root: Path, *, worker_primary: str = "steady-4c", teacher: str = "teacher-strong") -> None:
    path = ModelRoutingTableInitializer(root).initialize(overwrite=True)
    table = ModelRoutingTable.parse_yaml(path.read_text(encoding="utf-8"))
    routes = table.model_dump(mode="json")["routes"]
    routes["worker"] = {"primary": worker_primary, "fallback": "weak-backup"}
    routes["teacher_debug"] = {"primary": teacher}
    path.write_text(ModelRoutingTable.model_validate({"routes": routes}).render_yaml(), encoding="utf-8")


def _write_apply_evidence(root: Path, proposal_id: str = "wave4-4c-routing-apply-smoke") -> None:
    evidence_dir = root / ".hermes" / "routing-proposals" / proposal_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "apply-evidence.json").write_text(
        json.dumps(
            {
                "proposal_id": proposal_id,
                "status": "applied",
                "routing_table_mutated": True,
                "reason_codes": ["routing_proposal_approval_applies"],
                "applied_routes": {"worker": {"primary": "steady-4c"}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _plan(project_root: Path):
    _write_routing(project_root)
    _write_apply_evidence(project_root)
    return MultiWorkerOrchestrationPlanner(project_root).write_plan(
        plan_id="wave4-5b-plan",
        task_id="task.wave4-5b",
        required_capabilities=["python"],
        risk_level="low",
    )


def _contract() -> TaskContract:
    return TaskContract(
        task_id="task.wave4-5b",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Use approved multi-worker plan; dry-run only.",
    )


def _exact_authorization(plan_id: str = "wave4-5b-plan") -> MultiWorkerWorkflowDryRunAuthorization:
    return MultiWorkerWorkflowDryRunAuthorization(
        authorization_id="auth.wave4-5b",
        authorized_by="test-suite",
        plan_id=plan_id,
        task_id="task.wave4-5b",
        approved_action="execute_multi_worker_workflow_dry_run",
        worker_profile_ids=["steady-4c"],
        dry_run_only=True,
        max_profile_calls=1,
        scopes=["multi_worker_workflow_execute"],
        reason="Approve provider-free routed dry-run execution with fake runner.",
    )


def test_approved_multi_worker_dry_run_executes_selected_worker_without_promotion(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    plan = _plan(tmp_path)
    runner = FakeProfileRunner(
        {"steady-4c": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})}
    )

    report = MultiWorkerWorkflowDryRunOrchestrator(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=plan,
        authorization=_exact_authorization(),
        run_id="wave4-5b-approved-dry-run",
    )

    assert report.status == MultiWorkerWorkflowDryRunStatus.VERIFIED
    assert report.plan_id == "wave4-5b-plan"
    assert report.worker_profile == "steady-4c"
    assert report.provider_call_count == 1
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.global_hermes_config_mutated is False
    assert "multi_worker_plan_authorization_applies" in report.reason_codes
    assert report.workflow_report is not None
    assert report.workflow_report.status == "verified"
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    evidence_path = tmp_path / ".hermes" / "multi-worker-workflows" / "wave4-5b-approved-dry-run" / "evidence.json"
    assert evidence_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["status"] == "verified"
    assert payload["promotion_attempted"] is False


class RecordingProfileRunner:
    def __init__(self) -> None:
        self.requests: list[ProfileRunRequest] = []

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        self.requests.append(request)
        return ProfileRunResult(stdout="{}", stderr="", exit_code=0)


def test_multi_worker_dry_run_blocks_without_exact_authorization_before_profile_calls(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    plan = _plan(tmp_path)
    runner = RecordingProfileRunner()

    report = MultiWorkerWorkflowDryRunOrchestrator(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=plan,
        authorization=None,
        run_id="wave4-5b-missing-auth",
    )

    assert report.status == MultiWorkerWorkflowDryRunStatus.BLOCKED
    assert report.provider_call_count == 0
    assert report.workflow_report is None
    assert "missing_multi_worker_workflow_authorization" in report.reason_codes
    assert runner.requests == []


def test_multi_worker_dry_run_blocks_when_plan_needs_teacher_escalation(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_routing(tmp_path)
    blocked_plan = MultiWorkerOrchestrationPlanner(tmp_path).write_plan(
        plan_id="wave4-5b-blocked-plan",
        task_id="task.wave4-5b",
        required_capabilities=["python"],
        risk_level="medium",
        student_failure_count=2,
        teacher_call_budget=1,
    )
    runner = RecordingProfileRunner()

    report = MultiWorkerWorkflowDryRunOrchestrator(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=blocked_plan,
        authorization=_exact_authorization(plan_id="wave4-5b-blocked-plan"),
        run_id="wave4-5b-blocked-plan",
    )

    assert report.status == MultiWorkerWorkflowDryRunStatus.BLOCKED
    assert report.provider_call_count == 0
    assert "multi_worker_plan_not_selected" in report.reason_codes
    assert "teacher_escalation_authorization_missing" in report.reason_codes
    assert runner.requests == []


def test_runs_cli_shows_multi_worker_workflow_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    plan = _plan(tmp_path)
    runner = FakeProfileRunner(
        {"steady-4c": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})}
    )
    MultiWorkerWorkflowDryRunOrchestrator(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=plan,
        authorization=_exact_authorization(),
        run_id="wave4-5b-cli-evidence",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "multi-worker-workflow",
            "wave4-5b-cli-evidence",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["run_id"] == "wave4-5b-cli-evidence"
    assert payload["status"] == "verified"
    assert payload["worker_profile"] == "steady-4c"
    assert payload["promotion_attempted"] is False


def test_multi_worker_dry_run_rejects_mismatched_plan_authorization(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    plan = _plan(tmp_path)
    runner = RecordingProfileRunner()
    wrong = _exact_authorization(plan_id="different-plan")

    report = MultiWorkerWorkflowDryRunOrchestrator(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=plan,
        authorization=wrong,
        run_id="wave4-5b-wrong-auth",
    )

    assert report.status == MultiWorkerWorkflowDryRunStatus.BLOCKED
    assert report.provider_call_count == 0
    assert "authorization_plan_id_mismatch" in report.reason_codes
    assert runner.requests == []
