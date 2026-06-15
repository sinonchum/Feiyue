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
from feiyue_core.workflow.profile_worker_bridge import ProfileWorkflowBridge, ProfileWorkflowBridgeAuthorization
from feiyue_core.workflow.task_contract import build_task_contract


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
        "print('phase-b verifier passed')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "phase-b@example.invalid"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Feiyue Phase B"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "calc.py", "test_calc.py", "pytest.py"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed phase b source"], cwd=source, check=True, capture_output=True, text=True)


def _summary_markdown(payload: dict[str, object]) -> str:
    workflow = payload.get("workflow_report") or {}
    if not isinstance(workflow, dict):
        workflow = {}
    lines = [
        f"# Phase B Qwen2.5-Coder Workflow Benchmark: {payload['run_id']}",
        "",
        f"- status: {payload['status']}",
        f"- worker_profile: {payload['worker_profile']}",
        f"- model: {payload['model']}",
        f"- provider_call_count: {payload['provider_call_count']}",
        f"- repair_attempt_count: {payload['repair_attempt_count']}",
        f"- verification_passed: {workflow.get('verification_passed')}",
        f"- changed_files: {workflow.get('changed_files')}",
        f"- verification_command: {workflow.get('verification_command')}",
        "- safety: dry_run_only=true, promotion_attempted=false, global_hermes_config_mutated=false, production_mutated=false",
        "",
        "## Reason Codes",
    ]
    for reason in payload.get("reason_codes", []):
        lines.append(f"- {reason}")
    lines.extend(["", "## Ollama Calls"])
    for call in payload.get("ollama_calls", []):
        if isinstance(call, dict):
            lines.append(
                f"- role={call.get('role')} exit={call.get('exit_code')} latency_ms={float(call.get('latency_ms', 0)):.1f} "
                f"response_chars={call.get('response_chars')} source_ids={call.get('source_ids')}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase B local Qwen2.5-Coder through Feiyue ProfileWorkflowBridge.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--run-id", default=f"local-qwen25-coder-phase-b-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen2.5-coder:7b-instruct")
    parser.add_argument("--profile", default="local-qwen25-coder")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--num-predict", type=int, default=768)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    source = project_root / ".hermes" / "phase-b-sources" / args.run_id / "source"
    _seed_source(source)

    contract = build_task_contract(
        task_id="task.local-qwen25.phase-b.add-bugfix",
        title="Fix calc.add to return a sum",
        scope=(
            "Modify calc.py only. Replace the buggy multiplication implementation with a complete file that defines "
            "def add(a, b): return a + b. Output must be Feiyue candidate-writes JSON."
        ),
        files_to_modify=["calc.py"],
        files_not_to_touch=["test_calc.py", "~/.hermes", "README.md"],
        requirements=[
            "writes must be a non-empty list",
            "write path must be calc.py",
            "content must contain def add(a, b) and return a + b",
        ],
        acceptance_criteria=["python -m pytest -q passes in sandbox"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="If candidate-writes JSON cannot be parsed, perform one local repair retry before teacher escalation.",
    )

    ollama = OllamaProfileRunner(
        endpoint=args.endpoint,
        model_map={args.profile: args.model},
        temperature=0,
        num_predict=args.num_predict,
        timeout_seconds=args.timeout_seconds,
    )
    repairing_runner = CandidateWriteRepairingProfileRunner(inner=ollama, max_repair_attempts=1)
    report = ProfileWorkflowBridge(profile_runner=repairing_runner).execute(
        source_repo=source,
        contract=contract,
        project_name="phase-b-local-qwen25-toy-calc",
        worker_profile=args.profile,
        authorization=ProfileWorkflowBridgeAuthorization(scopes=["profile_workflow_execute"], max_profile_calls=2),
    )

    out_dir = project_root / ".hermes" / "phase-b-workflow-benchmarks" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "feiyue.local_qwen25.phase_b.v1",
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": str(report.status.value if hasattr(report.status, "value") else report.status),
        "worker_profile": args.profile,
        "model": args.model,
        "backend": "ollama",
        "provider_call_count": report.provider_call_count,
        "repair_attempt_count": repairing_runner.repair_attempt_count,
        "last_parse_error": repairing_runner.last_parse_error,
        "reason_codes": report.reason_codes,
        "workflow_report": report.workflow_report.model_dump(mode="json") if report.workflow_report else None,
        "stdout_redacted": report.stdout_redacted,
        "stderr_redacted": report.stderr_redacted,
        "ollama_calls": [call.model_dump(mode="json") for call in ollama.calls],
        "source_repo": str(source),
        "safety_flags": {
            "dry_run_only": True,
            "promotion_attempted": False,
            "global_hermes_config_mutated": False,
            "production_mutated": False,
        },
    }
    json_path = out_dir / "evidence.json"
    md_path = out_dir / "evidence.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_summary_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "run_id": args.run_id,
        "status": payload["status"],
        "provider_call_count": report.provider_call_count,
        "repair_attempt_count": repairing_runner.repair_attempt_count,
        "workflow_status": payload["workflow_report"]["status"] if payload["workflow_report"] else None,
        "verification_passed": payload["workflow_report"]["verification_passed"] if payload["workflow_report"] else None,
        "evidence_paths": [str(json_path), str(md_path)],
    }, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
