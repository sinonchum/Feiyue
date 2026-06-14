from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.providers.profile_runner import FakeProfileRunner, ProfileRunRequest, ProfileRunResult
from feiyue_core.workflow.capability_history import CapabilityHistoryCollector
from feiyue_core.workflow.model_routing_table import ModelRoutingTable, ModelRoutingTableInitializer
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlanner
from feiyue_core.workflow.real_multi_worker_live_dry_run import (
    RealMultiWorkerLiveDryRunAuthorization,
    RealMultiWorkerLiveDryRunExecutor,
    RealMultiWorkerLiveDryRunStatus,
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


def _write_routing(root: Path) -> None:
    path = ModelRoutingTableInitializer(root).initialize(overwrite=True)
    table = ModelRoutingTable.parse_yaml(path.read_text(encoding="utf-8"))
    routes = table.model_dump(mode="json")["routes"]
    routes["worker"] = {"primary": "steady-4c", "fallback": "weak-backup"}
    routes["teacher_debug"] = {"primary": "teacher-strong"}
    path.write_text(ModelRoutingTable.model_validate({"routes": routes}).render_yaml(), encoding="utf-8")


def _write_apply_evidence(root: Path, proposal_id: str = "wave5-3-routing-apply-smoke") -> None:
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
        plan_id="wave5-3-plan",
        task_id="task.wave5-3",
        required_capabilities=["python"],
        risk_level="low",
    )


def _contract() -> TaskContract:
    return TaskContract(
        task_id="task.wave5-3",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Use approved real multi-worker live dry-run only.",
    )


def _auth(run_id: str = "wave5-3-real-live-dry-run") -> RealMultiWorkerLiveDryRunAuthorization:
    return RealMultiWorkerLiveDryRunAuthorization(
        authorization_id="auth.wave5-3.real-live-dry-run",
        authorized_by="test-suite",
        plan_id="wave5-3-plan",
        run_id=run_id,
        task_id="task.wave5-3",
        approved_action="execute_real_multi_worker_live_dry_run",
        worker_profile_id="steady-4c",
        scopes=["real_multi_worker_live_dry_run_execute"],
        max_profile_calls=1,
        dry_run_only=True,
        budget_ceiling="0.01 USD",
        reason="Approve dry-run-only fake-first seam for real multi-worker history evidence.",
    )


class RecordingProfileRunner:
    def __init__(self) -> None:
        self.requests: list[ProfileRunRequest] = []

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        self.requests.append(request)
        return ProfileRunResult(stdout="{}", stderr="", exit_code=0)


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = f"{source_path}{os.pathsep}{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else source_path
    return env


def test_real_multi_worker_live_dry_run_blocks_missing_auth_before_profile_calls(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    plan = _plan(tmp_path)
    runner = RecordingProfileRunner()

    evidence = RealMultiWorkerLiveDryRunExecutor(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=plan,
        authorization=None,
        run_id="wave5-3-missing-auth",
    )

    assert evidence.status == RealMultiWorkerLiveDryRunStatus.BLOCKED
    assert evidence.provider_call_count == 0
    assert evidence.cost_usd == 0
    assert evidence.latency_ms == 0
    assert evidence.dry_run_only is True
    assert evidence.source_clean is True
    assert evidence.promotion_attempted is False
    assert evidence.global_hermes_config_mutated is False
    assert "missing_real_multi_worker_live_dry_run_authorization" in evidence.reason_codes
    assert runner.requests == []
    payload = json.loads((tmp_path / ".hermes" / "real-multi-worker-runs" / "wave5-3-missing-auth" / "evidence.json").read_text())
    assert payload["provider_call_count"] == 0


def test_real_multi_worker_live_dry_run_exact_auth_records_history_compatible_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    plan = _plan(tmp_path)
    runner = FakeProfileRunner(
        {"steady-4c": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})}
    )

    evidence = RealMultiWorkerLiveDryRunExecutor(profile_runner=runner).run(
        project_root=tmp_path,
        source_repo=repo,
        contract=_contract(),
        project_name="toy-calculator",
        plan=plan,
        authorization=_auth(),
        run_id="wave5-3-real-live-dry-run",
        cost_usd=0.0042,
        latency_ms=1234.5,
    )

    assert evidence.status == RealMultiWorkerLiveDryRunStatus.VERIFIED
    assert evidence.worker_profile == "steady-4c"
    assert evidence.provider_call_count == 1
    assert evidence.cost_usd == 0.0042
    assert evidence.latency_ms == 1234.5
    assert evidence.source_clean is True
    assert evidence.dry_run_only is True
    assert evidence.global_hermes_config_mutated is False
    assert evidence.promotion_attempted is False
    assert "real_multi_worker_live_dry_run_authorization_applies" in evidence.reason_codes
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"

    evidence_path = tmp_path / ".hermes" / "real-multi-worker-runs" / "wave5-3-real-live-dry-run" / "evidence.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["source_kind"] == "real_multi_worker_live_dry_run"
    assert payload["status"] == "verified"
    assert payload["cost_usd"] == 0.0042
    assert payload["latency_ms"] == 1234.5

    history = CapabilityHistoryCollector(tmp_path).build_report()
    real_records = [record for record in history.records if record.run_id == "wave5-3-real-live-dry-run" and record.source_kind == "real_multi_worker_live_dry_run"]
    assert len(real_records) == 1
    record = real_records[0]
    assert record.profile_id == "steady-4c"
    assert record.provider_call_count == 1
    assert record.cost_usd == 0.0042
    assert record.latency_ms == 1234.5
    assert record.promotion_attempted is False


def test_runs_cli_real_multi_worker_live_dry_run_fake_first(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _plan(tmp_path)
    auth_path = tmp_path / "real-auth.json"
    auth_path.write_text(_auth(run_id="wave5-3-cli-real-live").model_dump_json(indent=2), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "real-multi-worker-live-dry-run",
            "--plan-id",
            "wave5-3-plan",
            "--run-id",
            "wave5-3-cli-real-live",
            "--source-repo",
            str(repo),
            "--project-name",
            "toy-calculator",
            "--task-id",
            "task.wave5-3",
            "--title",
            "Fix calculator add",
            "--scope",
            "Make add return a sum.",
            "--file-to-modify",
            "calc.py",
            "--verification-command",
            "python -m pytest -q",
            "--authorization-path",
            str(auth_path),
            "--profile-runner",
            "fake",
            "--fake-worker-response-json",
            json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]}),
            "--cost-usd",
            "0.002",
            "--latency-ms",
            "987.0",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=_cli_env(),
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["run_id"] == "wave5-3-cli-real-live"
    assert payload["status"] == "verified"
    assert payload["provider_call_count"] == 1
    assert payload["cost_usd"] == 0.002
    assert payload["latency_ms"] == 987.0
    assert payload["promotion_attempted"] is False
    assert (tmp_path / ".hermes" / "real-multi-worker-runs" / "wave5-3-cli-real-live" / "evidence.json").exists()
