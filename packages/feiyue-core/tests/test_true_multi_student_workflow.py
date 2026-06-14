from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.providers.profile_runner import FakeProfileRunner
from feiyue_core.workflow.task_contract import TaskContract
from feiyue_core.workflow.true_multi_student_workflow import (
    MultiStudentAssignment,
    MultiStudentDryRunApproval,
    MultiStudentDryRunExecutor,
    MultiStudentDryRunStatus,
    MultiStudentPlan,
    assignment_hash,
)
from feiyue_core.workflow.promotion_lifecycle import (
    DraftPRStatus,
    approve_draft_pr,
    create_approved_draft_pr,
    create_multi_student_pr_plan,
)


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = f"{source_path}{os.pathsep}{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else source_path
    return env


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    (repo / "README.md").write_text("# Toy\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, text=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, text=True, capture_output=True)


def _contract() -> TaskContract:
    return TaskContract(
        task_id="task.true-multi-student",
        title="Fix add and docs",
        scope="Implementation worker fixes calc.py; docs worker updates README.",
        files_to_modify=["calc.py", "README.md"],
        acceptance_criteria=["pytest passes", "README updated"],
        verification_commands=["python -m pytest -q", "grep -q MULTI_STUDENT README.md"],
        escalation_rule="No teacher escalation; dry-run only.",
    )


def _plan(plan_id: str = "plan.true-multi-student") -> MultiStudentPlan:
    assignments = [
        MultiStudentAssignment(
            assignment_id="impl",
            profile_id="student-impl",
            role="implementation",
            capabilities=["python"],
            allowed_files=["calc.py"],
            max_profile_calls=1,
        ),
        MultiStudentAssignment(
            assignment_id="docs",
            profile_id="student-docs",
            role="docs",
            capabilities=["documentation"],
            allowed_files=["README.md"],
            max_profile_calls=1,
        ),
    ]
    return MultiStudentPlan(
        plan_id=plan_id,
        task_id="task.true-multi-student",
        worker_assignments=assignments,
        merge_strategy="reject_on_conflict",
        verifier_strategy="per_assignment_then_combined",
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        reason_codes=["true_multi_student_assignments_selected"],
    )


def _approval(plan: MultiStudentPlan, assignments_hash: str | None = None) -> MultiStudentDryRunApproval:
    return MultiStudentDryRunApproval(
        approval_id="approval.true-multi-student",
        approved_by="test-suite",
        plan_id=plan.plan_id,
        task_id=plan.task_id,
        approved_action="execute_true_multi_student_dry_run",
        worker_assignment_hash=assignments_hash or assignment_hash(plan.worker_assignments),
        worker_profile_ids=[a.profile_id for a in plan.worker_assignments],
        merge_strategy=plan.merge_strategy,
        verifier_strategy=plan.verifier_strategy,
        dry_run_only=True,
        max_total_profile_calls=2,
        reason="Approve true multi-student fake-first dry-run.",
    )


def _responses() -> dict[str, str]:
    return {
        "student-impl": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]}),
        "student-docs": json.dumps({"writes": [{"path": "README.md", "content": "# Toy\n\nMULTI_STUDENT docs updated.\n"}]}),
    }


def test_true_multi_student_executor_merges_disjoint_fake_workers_and_verifies(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    plan = _plan()

    report = MultiStudentDryRunExecutor(profile_runner=FakeProfileRunner(_responses())).run(
        project_root=tmp_path,
        source_repo=repo,
        project_name="toy",
        contract=_contract(),
        plan=plan,
        approval=_approval(plan),
        run_id="run.true-multi-student.fake",
    )

    assert report.status == MultiStudentDryRunStatus.VERIFIED
    assert report.provider_call_count == 2
    assert [a.assignment_id for a in report.assignment_reports] == ["impl", "docs"]
    assert report.merge_strategy == "reject_on_conflict"
    assert report.conflict_files == []
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.global_hermes_config_mutated is False
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    evidence = tmp_path / ".hermes" / "multi-student-workflows" / "run.true-multi-student.fake" / "evidence.json"
    assert evidence.exists()


def test_true_multi_student_executor_blocks_approval_hash_mismatch_before_calls(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    plan = _plan()
    report = MultiStudentDryRunExecutor(profile_runner=FakeProfileRunner(_responses())).run(
        project_root=tmp_path,
        source_repo=repo,
        project_name="toy",
        contract=_contract(),
        plan=plan,
        approval=_approval(plan, assignments_hash="wrong"),
        run_id="run.true-multi-student.bad-approval",
    )

    assert report.status == MultiStudentDryRunStatus.BLOCKED
    assert report.provider_call_count == 0
    assert "approval_assignment_hash_mismatch" in report.reason_codes


def test_true_multi_student_executor_blocks_conflicting_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    plan = _plan()
    plan.worker_assignments[1] = plan.worker_assignments[1].model_copy(update={"allowed_files": ["calc.py"]})
    conflict_responses = {
        "student-impl": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]}),
        "student-docs": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return 3\n"}]}),
    }

    report = MultiStudentDryRunExecutor(profile_runner=FakeProfileRunner(conflict_responses)).run(
        project_root=tmp_path,
        source_repo=repo,
        project_name="toy",
        contract=_contract(),
        plan=plan,
        approval=_approval(plan),
        run_id="run.true-multi-student.conflict",
    )

    assert report.status == MultiStudentDryRunStatus.BLOCKED
    assert "merge_conflict_reject_on_conflict" in report.reason_codes
    assert report.conflict_files == ["calc.py"]
    assert report.promotion_attempted is False


def test_true_multi_student_cli_approves_runs_and_inspects_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().model_dump_json(indent=2), encoding="utf-8")

    approve = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "approve-true-multi-student-dry-run",
            "--plan-path",
            str(plan_path),
            "--approved-by",
            "test-suite",
            "--approval-id",
            "approval.true-multi-student.cli",
            "--reason",
            "Approve CLI fake-first true multi-student run.",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=_cli_env(),
    )
    assert approve.returncode == 0, approve.stderr or approve.stdout

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "run-approved-true-multi-student-dry-run",
            "--plan-id",
            "plan.true-multi-student",
            "--run-id",
            "run.true-multi-student.cli",
            "--source-repo",
            str(repo),
            "--project-name",
            "toy",
            "--task-id",
            "task.true-multi-student",
            "--title",
            "Fix add and docs",
            "--scope",
            "Implementation worker fixes calc.py; docs worker updates README.",
            "--file-to-modify",
            "calc.py",
            "--file-to-modify",
            "README.md",
            "--verification-command",
            "python -m pytest -q",
            "--verification-command",
            "grep -q MULTI_STUDENT README.md",
            "--fake-response",
            "student-impl=" + _responses()["student-impl"],
            "--fake-response",
            "student-docs=" + _responses()["student-docs"],
        ],
        text=True,
        capture_output=True,
        check=False,
        env=_cli_env(),
    )
    assert run.returncode == 0, run.stderr or run.stdout
    payload = json.loads(run.stdout)
    assert payload["status"] == "verified"
    assert payload["provider_call_count"] == 2

    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "true-multi-student-workflow",
            "run.true-multi-student.cli",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=_cli_env(),
    )
    assert inspect.returncode == 0
    inspected = json.loads(inspect.stdout)
    assert inspected["run_id"] == "run.true-multi-student.cli"
    assert inspected["status"] == "verified"


def test_6a_verified_true_multi_student_run_can_create_approved_local_draft_pr_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    plan = _plan()
    report = MultiStudentDryRunExecutor(profile_runner=FakeProfileRunner(_responses())).run(
        project_root=repo,
        source_repo=repo,
        project_name="toy",
        contract=_contract(),
        plan=plan,
        approval=_approval(plan),
        run_id="run.true-multi-student.6a",
    )
    assert report.status == MultiStudentDryRunStatus.VERIFIED

    pr_plan = create_multi_student_pr_plan(
        project_root=repo,
        run_id="run.true-multi-student.6a",
        source_branch="candidate/true-multi-student-6a",
        target_branch="main",
    )

    assert pr_plan.status == "planned"
    assert pr_plan.external_pr_created is False
    assert pr_plan.mutates_production is False
    assert pr_plan.draft is True
    assert pr_plan.source_branch == "candidate/true-multi-student-6a"
    assert pr_plan.target_branch == "main"
    assert "multi_student_evidence" in pr_plan.evidence_refs
    assert "true multi-student" in pr_plan.body

    approval = approve_draft_pr(
        project_root=repo,
        run_id="run.true-multi-student.6a",
        approved_by="test-suite",
        approval_id="approval.true-multi-student.6a",
        reason="Approve fake draft PR evidence only.",
    )
    evidence = create_approved_draft_pr(project_root=repo, run_id="run.true-multi-student.6a", approval=approval)

    assert evidence.status == DraftPRStatus.CREATED
    assert evidence.approval_applies is True
    assert evidence.external_pr_created is False
    assert evidence.draft is True
    assert evidence.auto_merge is False
    assert evidence.mutates_production is False
