from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from feiyue_core.workflow.model_routing_table import ModelRoutingTable, ModelRoutingTableInitializer
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlanner, MultiWorkerPlanError


def _write_routing(root: Path, *, worker_primary: str = "steady-4c", worker_fallback: str = "weak-backup", teacher: str = "teacher-strong") -> Path:
    path = ModelRoutingTableInitializer(root).initialize(overwrite=True)
    table = ModelRoutingTable.parse_yaml(path.read_text(encoding="utf-8"))
    routes = table.model_dump(mode="json")["routes"]
    routes["worker"] = {"primary": worker_primary, "fallback": worker_fallback}
    routes["teacher_debug"] = {"primary": teacher}
    path.write_text(ModelRoutingTable.model_validate({"routes": routes}).render_yaml(), encoding="utf-8")
    return path


def _write_apply_evidence(root: Path, proposal_id: str = "wave4-4c-routing-apply-smoke") -> Path:
    evidence_dir = root / ".hermes" / "routing-proposals" / proposal_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "apply-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "proposal_id": proposal_id,
                "status": "applied",
                "routing_table_mutated": True,
                "reason_codes": ["routing_proposal_approval_applies"],
                "applied_routes": {"worker": {"primary": "steady-4c"}},
                "source_feedback_hash": "sha256:feedback",
                "current_routing_hash": "sha256:routing",
                "recommended_changes_hash": "sha256:changes",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return evidence_path


def test_multi_worker_orchestration_uses_applied_routing_without_provider_execution(tmp_path: Path) -> None:
    _write_routing(tmp_path)
    _write_apply_evidence(tmp_path)

    plan = MultiWorkerOrchestrationPlanner(tmp_path).plan(
        plan_id="wave4-5-plan",
        task_id="task.wave4-5.low-risk",
        required_capabilities=["python"],
        risk_level="low",
    )

    assert plan.route.status == "selected"
    assert plan.route.worker_profile_ids == ["steady-4c"]
    assert plan.route.provider_call_count == 0
    assert plan.provider_execution_requested is False
    assert plan.global_hermes_config_mutated is False
    assert plan.routing_apply_evidence_id == "wave4-4c-routing-apply-smoke"
    assert "routing_apply_evidence_loaded" in plan.reason_codes
    assert plan.selected_route_source == ".hermes/model-routing.yaml"


def test_multi_worker_orchestration_blocks_teacher_escalation_without_authorization(tmp_path: Path) -> None:
    _write_routing(tmp_path)

    plan = MultiWorkerOrchestrationPlanner(tmp_path).plan(
        plan_id="wave4-5-needs-teacher",
        task_id="task.wave4-5.needs-teacher",
        required_capabilities=["python"],
        risk_level="medium",
        student_failure_count=2,
        teacher_call_budget=1,
    )

    assert plan.route.status == "blocked"
    assert plan.route.worker_profile_ids == ["steady-4c"]
    assert plan.route.teacher_profile_id == "teacher-strong"
    assert plan.route.requires_teacher_authorization is True
    assert "teacher_escalation_authorization_missing" in plan.route.reason_codes
    assert plan.provider_execution_requested is False
    assert plan.global_hermes_config_mutated is False


def test_multi_worker_orchestration_writes_local_plan_evidence_without_routing_mutation(tmp_path: Path) -> None:
    routing_path = _write_routing(tmp_path)
    before = routing_path.read_text(encoding="utf-8")
    _write_apply_evidence(tmp_path)

    plan = MultiWorkerOrchestrationPlanner(tmp_path).write_plan(
        plan_id="wave4-5-written-plan",
        task_id="task.wave4-5.written",
        required_capabilities=["python"],
        risk_level="low",
    )

    assert routing_path.read_text(encoding="utf-8") == before
    plan_path = tmp_path / ".hermes" / "multi-worker-plans" / "wave4-5-written-plan" / "plan.json"
    markdown_path = tmp_path / ".hermes" / "multi-worker-plans" / "wave4-5-written-plan" / "plan.md"
    assert plan_path.exists()
    assert markdown_path.exists()
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload["plan_id"] == plan.plan_id
    assert payload["route"]["worker_profile_ids"] == ["steady-4c"]
    assert payload["global_hermes_config_mutated"] is False
    assert "provider_execution_requested: false" in markdown_path.read_text(encoding="utf-8")


def test_multi_worker_orchestration_fails_closed_when_routing_table_missing(tmp_path: Path) -> None:
    with pytest.raises(MultiWorkerPlanError, match="model routing table not found"):
        MultiWorkerOrchestrationPlanner(tmp_path).plan(
            plan_id="wave4-5-missing-routing",
            task_id="task.wave4-5.missing-routing",
            required_capabilities=["python"],
            risk_level="low",
        )


def test_runs_cli_writes_multi_worker_plan(tmp_path: Path) -> None:
    _write_routing(tmp_path)
    _write_apply_evidence(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "multi-worker-plan",
            "--plan-id",
            "wave4-5-cli-plan",
            "--task-id",
            "task.wave4-5.cli",
            "--capability",
            "python",
            "--risk-level",
            "low",
            "--write-plan",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["plan_id"] == "wave4-5-cli-plan"
    assert payload["route"]["worker_profile_ids"] == ["steady-4c"]
    assert payload["provider_execution_requested"] is False
    assert payload["global_hermes_config_mutated"] is False
    assert (tmp_path / ".hermes" / "multi-worker-plans" / "wave4-5-cli-plan" / "plan.json").exists()
