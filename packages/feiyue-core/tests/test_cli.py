import json
import subprocess
import sys

from feiyue_core.providers.profile_runner import FakeProfileRunner
from feiyue_core.workflow import TaskContract
from feiyue_core.workflow.real_profile_workflow_runner import RealProfileWorkflowAuthorization, RealProfileWorkflowRunner


def test_interruption_demo_cli_outputs_recovery_summary_json(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.runtime.interruption_simulation",
            "--root",
            str(tmp_path / "demo"),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["pending_operations"] == []
    assert payload["warnings"] == []
    assert payload["next_safe_action"] == "continue with next planned step"
    assert payload["verified_count"] == 3
    assert payload["file_exists"] is True
    assert payload["artifact_exists"] is True
    assert "Pending / unknown operations" in payload["recovery_prompt"]


def _write_run_evidence(root, task_id="m12-cli-demo"):
    run_dir = root / ".hermes" / "runs" / task_id
    run_dir.mkdir(parents=True)
    (run_dir / "run-evidence.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "status": "blocked",
                "policy_action": "escalate",
                "policy_reason": "high_risk_operation",
                "execution_performed": False,
                "retry_performed": False,
                "promotion_status": None,
                "promotion_side_effect_performed": None,
                "approval_exists": False,
                "approval_id": None,
                "approval_approver": None,
                "approval_action": None,
                "approval_applies": False,
                "safe_to_retry": False,
                "next_safe_action": "request_human_approval",
                "report_paths": {"execution_report": "execution-report.md", "execution_json": "execution-report.json"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_dir


def test_runs_cli_lists_persisted_run_ids(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m12-cli-demo")
    _write_run_evidence(tmp_path, "m12-cli-second")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "list"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout.splitlines() == ["m12-cli-demo", "m12-cli-second"]


def test_runs_cli_shows_run_evidence_json(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m12-cli-demo")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "show", "m12-cli-demo"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["task_id"] == "m12-cli-demo"
    assert payload["next_safe_action"] == "request_human_approval"
    assert payload["approval_exists"] is False


def test_runs_cli_renders_fallback_handoff_summary(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m12-cli-demo")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "handoff", "m12-cli-demo"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "# Fallback Handoff Summary" in completed.stdout
    assert "- task_id: m12-cli-demo" in completed.stdout
    assert "## Approval Evidence" in completed.stdout
    assert "- approval_exists: False" in completed.stdout


def test_runs_cli_missing_run_exits_nonzero_with_stable_error(tmp_path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "show", "missing-task"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "Run evidence index not found" in completed.stderr
    assert "missing-task" in completed.stderr


def test_runs_cli_lists_catalog_summary_as_json(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-cli-catalog")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "list", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["total_runs"] == 1
    assert payload["safe_to_retry_count"] == 0
    assert payload["next_action_counts"] == {"request_human_approval": 1}
    assert payload["runs"][0]["task_id"] == "m13-cli-catalog"
    assert payload["runs"][0]["approval_exists"] is False


def test_runs_cli_shows_real_profile_workflow_smoke_evidence(tmp_path) -> None:
    smoke_dir = tmp_path / ".hermes" / "workflow-smokes" / "w43a-dry-run"
    smoke_dir.mkdir(parents=True)
    (smoke_dir / "evidence.json").write_text(
        json.dumps(
            {
                "run_id": "w43a-dry-run",
                "status": "verified",
                "provider_call_count": 1,
                "dry_run_only": True,
                "promotion_attempted": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "workflow-smoke", "w43a-dry-run"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["run_id"] == "w43a-dry-run"
    assert payload["status"] == "verified"
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False


def test_runs_cli_shows_workflow_promotion_evidence(tmp_path) -> None:
    promotion_dir = tmp_path / ".hermes" / "workflow-promotions" / "w43b-dry-run"
    promotion_dir.mkdir(parents=True)
    (promotion_dir / "promotion-evidence.json").write_text(
        json.dumps(
            {
                "run_id": "w43b-dry-run",
                "status": "blocked",
                "approval_applies": False,
                "promotion_attempted": False,
                "reason_codes": ["missing_promotion_approval"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "workflow-promotion", "w43b-dry-run"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["run_id"] == "w43b-dry-run"
    assert payload["approval_applies"] is False
    assert payload["promotion_attempted"] is False
    assert payload["reason_codes"] == ["missing_promotion_approval"]


def _init_cli_toy_repo(repo) -> None:
    repo.mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["."]\n', encoding="utf-8")
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calc.py").write_text("from calc import add\n\n\ndef test_adds_numbers():\n    assert add(2, 3) == 5\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".hermes/workflow-smokes/\n.hermes/workflow-promotions/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)


def _write_cli_dry_run_evidence(repo, run_id="w43c-cli-flow") -> None:
    contract = TaskContract(
        task_id=run_id,
        title="Wave4-3C CLI approval flow",
        scope="Verify approval CLI and promote-approved CLI with an isolated branch.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Promotion requires productized approval evidence.",
    )
    runner = RealProfileWorkflowRunner(
        profile_runner=FakeProfileRunner(
            {"weak": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})}
        )
    )
    report = runner.run(
        source_repo=repo,
        contract=contract,
        project_name="cli-approval-flow",
        worker_profile="weak",
        teacher_profile=None,
        authorization=RealProfileWorkflowAuthorization(
            scopes=["real_profile_workflow_execute"],
            max_profile_calls=1,
            dry_run_only=True,
            allow_real_project=True,
        ),
        evidence_root=repo,
        run_id=run_id,
    )
    assert report.status == "verified"


def test_runs_cli_approves_and_promotes_verified_dry_run(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_cli_toy_repo(repo)
    _write_cli_dry_run_evidence(repo)

    approve = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-promotion",
            "w43c-cli-flow",
            "--target-branch",
            "feiyue/w43c-cli-approved",
            "--changed-file",
            "calc.py",
            "--approved-by",
            "Simon",
            "--approval-id",
            "approval-w43c-cli-001",
            "--reason",
            "Approve productized CLI promotion smoke.",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    approval_payload = json.loads(approve.stdout)
    assert approval_payload["run_id"] == "w43c-cli-flow"
    assert approval_payload["approved_action"] == "promote_verified_dry_run"
    assert approval_payload["changed_files"] == ["calc.py"]
    assert approval_payload["workflow_report_hash"]

    promote = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "promote-approved",
            "w43c-cli-flow",
            "--commit-message",
            "fix: promote approved cli smoke",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    promotion_payload = json.loads(promote.stdout)
    assert promotion_payload["status"] == "promoted"
    assert promotion_payload["approval_applies"] is True
    assert promotion_payload["promotion_attempted"] is True
    assert promotion_payload["target_branch"] == "feiyue/w43c-cli-approved"
    promoted = subprocess.run(["git", "show", "feiyue/w43c-cli-approved:calc.py"], cwd=repo, text=True, capture_output=True, check=True)
    assert promoted.stdout == "def add(a, b):\n    return a + b\n"
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
