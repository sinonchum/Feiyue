#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from feiyue_core.providers.ollama_runner import CandidateWriteRepairingProfileRunner, OllamaProfileRunner
from feiyue_core.routing.multi_worker_gate import RouteStatus, WorkerRoutePlan
from feiyue_core.workflow.capability_history import CapabilityHistoryCollector
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlan
from feiyue_core.workflow.real_multi_worker_live_dry_run import (
    RealMultiWorkerLiveDryRunAuthorization,
    RealMultiWorkerLiveDryRunExecutor,
)
from feiyue_core.workflow.task_contract import build_task_contract
from feiyue_core.workflow.wave9_task_pack import (
    Wave9TaskAssignment,
    Wave9TaskPack,
    Wave9TaskPackExecutor,
    approve_wave9_task_pack_execution,
    task_pack_hash,
    write_wave9_task_pack,
)


def _seed_source(source: Path) -> None:
    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)
    (source / "calc.py").write_text("def add(a, b):\n    return a * b\n", encoding="utf-8")
    (source / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add_returns_sum():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n",
        encoding="utf-8",
    )
    (source / "pytest.py").write_text(
        "from calc import add\n"
        "assert add(2, 3) == 5\n"
        "assert add(-1, 1) == 0\n"
        "print('phase-d verifier passed')\n",
        encoding="utf-8",
    )
    (source / "README.md").write_text("# Calculator\n\nPending docs update.\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "phase-d@example.invalid"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Feiyue Phase D"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "calc.py", "test_calc.py", "pytest.py", "README.md"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed phase d source"], cwd=source, check=True, capture_output=True, text=True)


def _build_wave9_pack(run_id: str, profile: str) -> Wave9TaskPack:
    pack = Wave9TaskPack(
        task_pack_id=f"pack.{run_id}",
        task_id=f"task.{run_id}.wave9.calc-add",
        title="Phase D Wave9-style local Qwen calculator patch",
        summary=(
            "Wave9-style dry-run task pack: one local weak worker assignment fixes calc.py; "
            "one local weak worker assignment updates README.md. No PR, merge, deployment, promotion, or production mutation."
        ),
        assignments=[
            Wave9TaskAssignment(
                assignment_id="impl-calc-add",
                profile_id=profile,
                role="implementation",
                objective=(
                    "Write exactly one candidate write for calc.py. The complete file content must be: "
                    "def add(a, b): return a + b. Do not write any other file."
                ),
                allowed_files=["calc.py"],
                verifier_commands=["python -m pytest -q"],
                max_profile_calls=1,
            ),
            Wave9TaskAssignment(
                assignment_id="docs-readme",
                profile_id=profile,
                role="docs",
                objective=(
                    "Write exactly one candidate write for README.md. Explain in one or two sentences that "
                    "calc.add returns the sum of two inputs and that verification uses python -m pytest -q. "
                    "Do not write calc.py or test files."
                ),
                allowed_files=["README.md"],
                verifier_commands=["python -m pytest -q"],
                max_profile_calls=1,
            ),
        ],
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest -q"],
        review_criteria=[
            "candidate writes stay inside assignment allowed_files",
            "combined verifier passes in sandbox",
            "dry-run evidence only; no PR/merge/deploy/promotion",
        ],
        reason_codes=["phase_d_wave9_style_pack", "local_qwen25_weak_worker", "dry_run_only"],
    )
    return pack


def _build_plan(run_id: str, profile: str, task_id: str) -> MultiWorkerOrchestrationPlan:
    return MultiWorkerOrchestrationPlan(
        plan_id=f"plan.{run_id}.real-multi-worker",
        task_id=task_id,
        route=WorkerRoutePlan(
            task_id=task_id,
            status=RouteStatus.SELECTED,
            worker_profile_ids=[profile],
            teacher_profile_id=None,
            requires_teacher_authorization=False,
            reason_codes=["worker_capability_match", "risk_within_worker_ceiling", "phase_d_local_qwen25_selected"],
            provider_call_count=0,
            audit_metadata={"phase": "D", "worker_role": "local weak implementation worker"},
        ),
        selected_route_source="phase-d-local-script",
        routing_apply_evidence_id=None,
        routing_apply_evidence_path=None,
        reason_codes=["phase_d_manual_route_plan", "provider_execution_requested_false", "global_hermes_config_not_mutated"],
        provider_execution_requested=False,
        global_hermes_config_mutated=False,
        audit_metadata={
            "required_capabilities": ["single_file_python_bugfix", "verifier_backed_patch"],
            "risk_level": "low",
            "available_teacher_profile_id": None,
            "writes_only_local_plan_evidence": True,
        },
    )


def _contract(run_id: str):
    return build_task_contract(
        task_id=f"task.{run_id}.real-multi-worker.calc-add",
        title="Phase D real multi-worker local Qwen calc.add patch",
        scope=(
            "Modify calc.py only. Replace the buggy multiplication implementation with a complete file that defines "
            "def add(a, b): return a + b. Output Feiyue candidate-writes JSON only."
        ),
        files_to_modify=["calc.py"],
        files_not_to_touch=["test_calc.py", "pytest.py", "README.md", "~/.hermes"],
        requirements=["write path must be calc.py", "content must implement addition", "verifier must pass"],
        acceptance_criteria=["python -m pytest -q passes in sandbox"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Phase D dry-run only; no promotion or production mutation.",
    )


def _summary_markdown(payload: dict[str, object]) -> str:
    wave9 = payload.get("wave9") if isinstance(payload.get("wave9"), dict) else {}
    real = payload.get("real_multi_worker") if isinstance(payload.get("real_multi_worker"), dict) else {}
    cap = payload.get("capability_history") if isinstance(payload.get("capability_history"), dict) else {}
    lines = [
        f"# Phase D Qwen2.5-Coder Wave9 / Real Multi-worker Dry-run: {payload['run_id']}",
        "",
        f"- status: {payload['status']}",
        f"- model: {payload['model']}",
        f"- profile: {payload['profile']}",
        f"- provider_call_count: {payload['provider_call_count']}",
        f"- wave9_status: {wave9.get('status')}",
        f"- real_multi_worker_status: {real.get('status')}",
        f"- capability_history_total_records: {cap.get('total_records')}",
        "- safety: dry_run_only=true, promotion_attempted=false, global_hermes_config_mutated=false, production_mutated=false, routing_table_mutated=false",
        "",
        "## Wave9 assignments",
    ]
    for item in wave9.get("assignment_reports", []) if isinstance(wave9, dict) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('assignment_id')}: status={item.get('status')}; files={item.get('candidate_files')}; allowed_scope={item.get('allowed_scope')}")
    lines.extend(["", "## Real multi-worker", f"- verified: {real.get('verified')}", f"- reason_codes: {real.get('reason_codes')}", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase D local Qwen2.5-Coder through Wave9 task-pack and real multi-worker dry-run seams.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--run-id", default=f"local-qwen25-coder-phase-d-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen2.5-coder:7b-instruct")
    parser.add_argument("--profile", default="local-qwen25-coder")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--num-predict", type=int, default=768)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    source = project_root / ".hermes" / "phase-d-sources" / args.run_id / "source"
    _seed_source(source)

    ollama = OllamaProfileRunner(
        endpoint=args.endpoint,
        model_map={args.profile: args.model},
        temperature=0,
        num_predict=args.num_predict,
        timeout_seconds=args.timeout_seconds,
    )
    runner = CandidateWriteRepairingProfileRunner(inner=ollama, max_repair_attempts=1)

    pack = _build_wave9_pack(args.run_id, args.profile)
    write_wave9_task_pack(pack, project_root)
    wave9_auth = approve_wave9_task_pack_execution(
        project_root=project_root,
        task_pack=pack,
        approval_id=f"approval.{args.run_id}.wave9",
        approved_by="phase-d-local-script",
        reason="Approve dry-run-only local Qwen2.5-Coder Wave9 task-pack benchmark.",
        max_total_profile_calls=2,
    )
    wave9_report = Wave9TaskPackExecutor(profile_runner=runner).run(
        project_root=project_root,
        source_repo=source,
        project_name="phase-d-local-qwen25-wave9-calculator",
        task_pack=pack,
        authorization=wave9_auth,
        run_id=f"{args.run_id}-wave9",
    )

    contract = _contract(args.run_id)
    plan = _build_plan(args.run_id, args.profile, contract.task_id)
    plan_dir = project_root / ".hermes" / "multi-worker-plans" / plan.plan_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    real_auth = RealMultiWorkerLiveDryRunAuthorization(
        authorization_id=f"auth.{args.run_id}.real-multi-worker",
        authorized_by="phase-d-local-script",
        plan_id=plan.plan_id,
        run_id=f"{args.run_id}-real-multi-worker",
        task_id=contract.task_id,
        approved_action="execute_real_multi_worker_live_dry_run",
        worker_profile_id=args.profile,
        scopes=["real_multi_worker_live_dry_run_execute"],
        max_profile_calls=1,
        budget_ceiling="local ollama only / zero external USD",
        dry_run_only=True,
        promotion_disabled=True,
        reason="Approve dry-run-only local Qwen2.5-Coder real multi-worker evidence path.",
    )
    before_real_calls = len(ollama.calls)
    real_evidence = RealMultiWorkerLiveDryRunExecutor(profile_runner=runner).run(
        project_root=project_root,
        source_repo=source,
        contract=contract,
        project_name="phase-d-local-qwen25-real-multi-worker-calculator",
        plan=plan,
        authorization=real_auth,
        run_id=f"{args.run_id}-real-multi-worker",
        cost_usd=0,
        latency_ms=sum(call.latency_ms for call in ollama.calls[before_real_calls:]),
    )

    cap_report = CapabilityHistoryCollector(project_root).write_report()
    profile_summary = cap_report.profile_summaries.get(args.profile)
    wave9_payload = wave9_report.model_dump(mode="json")
    real_payload = real_evidence.model_dump(mode="json")
    status = "verified" if wave9_payload.get("status") == "verified" and real_payload.get("status") == "verified" else "failed"
    payload = {
        "schema_version": "feiyue.local_qwen25.phase_d.v1",
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "profile": args.profile,
        "model": args.model,
        "backend": "ollama",
        "provider_call_count": wave9_report.provider_call_count + real_evidence.provider_call_count,
        "repair_attempt_count": runner.repair_attempt_count,
        "last_parse_error": runner.last_parse_error,
        "wave9": {
            **wave9_payload,
            "task_pack_hash": task_pack_hash(pack),
            "task_pack_path": str(project_root / ".hermes" / "wave9-task-packs" / pack.task_pack_id / "task-pack.json"),
            "authorization_path": str(project_root / ".hermes" / "wave9-task-packs" / pack.task_pack_id / "authorization.json"),
        },
        "real_multi_worker": real_payload,
        "ollama_calls": [call.model_dump(mode="json") for call in ollama.calls],
        "capability_history": {
            "total_records": cap_report.total_records,
            "profile_summary": profile_summary.model_dump(mode="json") if profile_summary else None,
            "latest_json": str(project_root / ".hermes" / "capability-history" / "latest.json"),
            "latest_md": str(project_root / ".hermes" / "capability-history" / "latest.md"),
        },
        "safety_flags": {
            "dry_run_only": True,
            "promotion_attempted": False,
            "global_hermes_config_mutated": False,
            "production_mutated": False,
            "routing_table_mutated": False,
        },
    }
    out_dir = project_root / ".hermes" / "phase-d-workflow-benchmarks" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evidence.json"
    md_path = out_dir / "evidence.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_summary_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "run_id": args.run_id,
        "status": status,
        "provider_call_count": payload["provider_call_count"],
        "wave9_status": wave9_payload.get("status"),
        "real_multi_worker_status": real_payload.get("status"),
        "capability_history": payload["capability_history"],
        "evidence_paths": [str(json_path), str(md_path)],
    }, indent=2, ensure_ascii=False))
    return 0 if status == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
