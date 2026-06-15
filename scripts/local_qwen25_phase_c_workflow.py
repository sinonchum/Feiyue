#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from feiyue_core.providers.ollama_runner import CandidateWriteRepairingProfileRunner, OllamaProfileRunner
from feiyue_core.providers.profile_runner import ProfileRunRequest
from feiyue_core.workflow.capability_history import CapabilityHistoryCollector
from feiyue_core.workflow.execution import CandidateFileWrite, ToyWorkflowExecutor
from feiyue_core.workflow.profile_worker_bridge import _parse_candidate_writes
from feiyue_core.workflow.task_contract import TaskContract, build_task_contract


@dataclass
class LaneResult:
    lane: str
    status: str
    task_id: str
    provider_call_count: int
    repair_attempt_count: int
    teacher_used: bool
    verification_passed: bool
    retry_performed: bool
    changed_files: list[str]
    stdout_redacted: list[str]
    workflow_report: dict[str, object]
    ollama_call_count_before: int
    ollama_call_count_after: int


def _seed_source(source: Path, *, broken_operator: str = "*") -> None:
    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)
    (source / "calc.py").write_text(f"def add(a, b):\n    return a {broken_operator} b\n", encoding="utf-8")
    (source / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add_returns_sum():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n",
        encoding="utf-8",
    )
    # Local pytest shim: keeps Feiyue's verifier command stable without depending on global pytest in Windows sandbox.
    (source / "pytest.py").write_text(
        "from calc import add\n"
        "assert add(2, 3) == 5\n"
        "assert add(-1, 1) == 0\n"
        "print('phase-c verifier passed')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "phase-c@example.invalid"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Feiyue Phase C"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "calc.py", "test_calc.py", "pytest.py"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed phase c source"], cwd=source, check=True, capture_output=True, text=True)


def _contract(task_id: str, *, escalation_rule: str) -> TaskContract:
    return build_task_contract(
        task_id=task_id,
        title="Fix calc.add to return a sum",
        scope=(
            "Modify calc.py only. Replace the buggy implementation with a complete file that defines "
            "def add(a, b): return a + b. Output must be Feiyue candidate-writes JSON."
        ),
        files_to_modify=["calc.py"],
        files_not_to_touch=["test_calc.py", "pytest.py", "~/.hermes", "README.md"],
        requirements=[
            "writes must be a non-empty list",
            "write path must be calc.py",
            "content must contain def add(a, b) and return a + b",
            "do not modify test_calc.py or pytest.py",
        ],
        acceptance_criteria=["python -m pytest -q passes in sandbox"],
        verification_commands=["python -m pytest -q"],
        escalation_rule=escalation_rule,
    )


def _retry_prompt(contract: TaskContract, *, first_report: object, teacher_guidance: str | None) -> str:
    payload = first_report.model_dump(mode="json")  # type: ignore[attr-defined]
    bug_dossier = payload.get("bug_dossier") or {}
    if not isinstance(bug_dossier, dict):
        bug_dossier = {}
    guidance = teacher_guidance or (
        "The verifier failed. Repair only calc.py. The intended semantic fix is addition: return a + b. "
        "Do not touch tests or config. Output strict Feiyue candidate-writes JSON."
    )
    return (
        "You are the local weak implementation worker in Feiyue Phase C.\n"
        "Return raw Feiyue candidate-writes JSON only; no markdown fences, no commentary.\n"
        "Required shape: {\"writes\":[{\"path\":\"calc.py\",\"content\":\"complete file content\"}]}.\n\n"
        f"Task contract:\n{contract.render_markdown()}\n\n"
        f"Verifier failure command: {bug_dossier.get('failing_command')}\n"
        f"Verifier error excerpt: {bug_dossier.get('error_excerpt')}\n\n"
        f"Guidance:\n{guidance}\n"
    )


def _run_lane(
    *,
    lane: str,
    project_root: Path,
    run_id: str,
    profile: str,
    model: str,
    runner: CandidateWriteRepairingProfileRunner,
    ollama: OllamaProfileRunner,
    teacher_guidance: str | None,
) -> LaneResult:
    source = project_root / ".hermes" / "phase-c-sources" / run_id / lane / "source"
    _seed_source(source)
    task_id = f"task.local-qwen25.phase-c.{lane}.add-bugfix"
    contract = _contract(
        task_id,
        escalation_rule=(
            "After an initial verifier failure, retry the local weak worker with verifier feedback."
            if teacher_guidance is None
            else "After an initial verifier failure, request sparse teacher guidance and retry the local weak worker once."
        ),
    )
    executor = ToyWorkflowExecutor()
    initial_writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")]
    first = executor.execute(source_repo=source, contract=contract, candidate_writes=initial_writes, project_name=f"phase-c-{lane}")
    before = len(ollama.calls)
    retry = runner.run(
        ProfileRunRequest(
            prompt=_retry_prompt(contract, first_report=first, teacher_guidance=teacher_guidance),
            role="worker",
            profile=profile,
            source_ids=(f"task:{task_id}", f"phase-c:{lane}", "verifier-retry" if teacher_guidance is None else "sparse-teacher-retry"),
        )
    )
    stdout_redacted = [retry.stdout]
    try:
        retry_writes = _parse_candidate_writes(retry.stdout)
        if teacher_guidance is None:
            final = executor.execute(source_repo=source, contract=contract, candidate_writes=retry_writes, project_name=f"phase-c-{lane}")
            final = final.model_copy(update={"retry_performed": True})
        else:
            final = executor.execute_with_teacher_retry(
                source_repo=source,
                contract=contract,
                initial_writes=initial_writes,
                teacher_guidance=teacher_guidance,
                revised_writes=retry_writes,
                project_name=f"phase-c-{lane}",
                max_attempts=2,
            )
    except Exception as exc:
        final = first.model_copy(update={"status": first.status, "retry_performed": False})
        stdout_redacted.append(f"phase-c parse/execution error: {type(exc).__name__}: {exc}")
    after = len(ollama.calls)
    final_payload = final.model_dump(mode="json")
    status = str(final_payload.get("status"))
    verification_passed = bool(final_payload.get("verification_passed"))
    workflow_payload = {
        **final_payload,
        "capability": "phase_c_local_qwen25_verifier_retry" if teacher_guidance is None else "phase_c_local_qwen25_sparse_teacher_retry",
    }
    # Write a collector-compatible workflow-smokes evidence file.
    workflow_dir = project_root / ".hermes" / "workflow-smokes" / f"{run_id}-{lane}"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "run_id": f"{run_id}-{lane}",
        "task_id": task_id,
        "status": status,
        "verified": verification_passed,
        "verification_passed": verification_passed,
        "worker_profile": profile,
        "teacher_profile": "synthetic-sparse-teacher" if teacher_guidance else None,
        "capability": workflow_payload["capability"],
        "provider_call_count": after - before + (1 if teacher_guidance else 0),
        "promotion_attempted": False,
        "dry_run_only": True,
        "workflow_report": workflow_payload,
        "stdout_redacted": stdout_redacted,
        "written_at": datetime.now(UTC).isoformat(),
    }
    (workflow_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return LaneResult(
        lane=lane,
        status=status,
        task_id=task_id,
        provider_call_count=after - before + (1 if teacher_guidance else 0),
        repair_attempt_count=runner.repair_attempt_count,
        teacher_used=teacher_guidance is not None,
        verification_passed=verification_passed,
        retry_performed=bool(final_payload.get("retry_performed")),
        changed_files=list(final_payload.get("changed_files") or []),
        stdout_redacted=stdout_redacted,
        workflow_report=workflow_payload,
        ollama_call_count_before=before,
        ollama_call_count_after=after,
    )


def _summary_markdown(payload: dict[str, object]) -> str:
    lines = [
        f"# Phase C Qwen2.5-Coder Workflow Benchmark: {payload['run_id']}",
        "",
        f"- model: {payload['model']}",
        f"- profile: {payload['profile']}",
        f"- status: {payload['status']}",
        f"- lanes_total: {payload['lanes_total']}",
        f"- lanes_verified: {payload['lanes_verified']}",
        f"- provider_call_count: {payload['provider_call_count']}",
        f"- weak_autonomy_rate: {payload['weak_autonomy_rate']}",
        f"- teacher_call_rate: {payload['teacher_call_rate']}",
        "- safety: dry_run_only=true, promotion_attempted=false, global_hermes_config_mutated=false, production_mutated=false",
        "",
        "## Lanes",
    ]
    for lane in payload.get("lanes", []):
        if isinstance(lane, dict):
            lines.extend([
                f"### {lane.get('lane')}",
                f"- status: {lane.get('status')}",
                f"- verification_passed: {lane.get('verification_passed')}",
                f"- retry_performed: {lane.get('retry_performed')}",
                f"- teacher_used: {lane.get('teacher_used')}",
                f"- provider_call_count: {lane.get('provider_call_count')}",
                f"- changed_files: {lane.get('changed_files')}",
                "",
            ])
    lines.append("## Capability History")
    cap = payload.get("capability_history")
    if isinstance(cap, dict):
        lines.append(f"- total_records: {cap.get('total_records')}")
        lines.append(f"- profile_summary: {cap.get('profile_summary')}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase C local Qwen2.5-Coder verifier retry + sparse teacher benchmark.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--run-id", default=f"local-qwen25-coder-phase-c-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen2.5-coder:7b-instruct")
    parser.add_argument("--profile", default="local-qwen25-coder")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--num-predict", type=int, default=768)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    ollama = OllamaProfileRunner(
        endpoint=args.endpoint,
        model_map={args.profile: args.model},
        temperature=0,
        num_predict=args.num_predict,
        timeout_seconds=args.timeout_seconds,
    )
    repairing_runner = CandidateWriteRepairingProfileRunner(inner=ollama, max_repair_attempts=1)
    lanes = [
        _run_lane(
            lane="weak-verifier-retry",
            project_root=project_root,
            run_id=args.run_id,
            profile=args.profile,
            model=args.model,
            runner=repairing_runner,
            ollama=ollama,
            teacher_guidance=None,
        ),
        _run_lane(
            lane="weak-sparse-teacher",
            project_root=project_root,
            run_id=args.run_id,
            profile=args.profile,
            model=args.model,
            runner=repairing_runner,
            ollama=ollama,
            teacher_guidance="Sparse teacher: the failure is caused by multiplication. Patch calc.py only and implement add as return a + b. Keep tests unchanged.",
        ),
    ]
    cap_report = CapabilityHistoryCollector(project_root).write_report()
    profile_summary = cap_report.profile_summaries.get(args.profile)
    lanes_verified = sum(1 for lane in lanes if lane.verification_passed)
    provider_call_count = sum(lane.provider_call_count for lane in lanes)
    teacher_count = sum(1 for lane in lanes if lane.teacher_used)
    payload = {
        "schema_version": "feiyue.local_qwen25.phase_c.v1",
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "verified" if lanes_verified == len(lanes) else "needs_teacher",
        "profile": args.profile,
        "model": args.model,
        "backend": "ollama",
        "lanes_total": len(lanes),
        "lanes_verified": lanes_verified,
        "weak_autonomy_rate": (len(lanes) - teacher_count) / len(lanes),
        "teacher_call_rate": teacher_count / len(lanes),
        "provider_call_count": provider_call_count,
        "repair_attempt_count": repairing_runner.repair_attempt_count,
        "last_parse_error": repairing_runner.last_parse_error,
        "lanes": [lane.__dict__ for lane in lanes],
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
    out_dir = project_root / ".hermes" / "phase-c-workflow-benchmarks" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evidence.json"
    md_path = out_dir / "evidence.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_summary_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "run_id": args.run_id,
        "status": payload["status"],
        "lanes_verified": lanes_verified,
        "lanes_total": len(lanes),
        "provider_call_count": provider_call_count,
        "teacher_call_rate": payload["teacher_call_rate"],
        "evidence_paths": [str(json_path), str(md_path)],
        "capability_history": payload["capability_history"],
    }, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
