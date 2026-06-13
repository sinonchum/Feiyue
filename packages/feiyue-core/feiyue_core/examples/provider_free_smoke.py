from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from feiyue_core.workflow.execution import (
    CandidateFileWrite,
    RunEvidenceLoader,
    ToyWorkflowExecutor,
    WorkflowReportWriter,
)
from feiyue_core.workflow.runs_export_all import export_static_runs_report_all
from feiyue_core.workflow.task_contract import TaskContract

TASK_ID = "m14-provider-free-example-smoke"


@dataclass(frozen=True)
class ProviderFreeExampleResult:
    task_id: str
    workflow_status: str
    promotion_status: str | None
    run_evidence_path: Path
    handoff_summary_path: Path
    report_index_path: Path
    manifest_path: Path
    bundle_path: Path
    extracted_dir: Path
    initial_verify: bool
    extracted_verify: bool


def run_provider_free_example(
    *,
    root: str | Path,
    out: str | Path,
    bundle: str | Path,
) -> ProviderFreeExampleResult:
    """Run Feiyue's provider-free workflow on a generated toy project.

    The smoke creates a tiny git repo, runs a failing student write followed by
    deterministic fake-teacher guidance and a corrected retry, persists run
    evidence, renders fallback handoff, then exports/verifies/bundles the static
    report. It does not call a model provider and does not mutate Hermes config.
    """

    project_root = Path(root)
    output_dir = Path(out)
    bundle_path = Path(bundle)
    _init_toy_project(project_root)

    contract = TaskContract(
        task_id=TASK_ID,
        title="Fix provider-free calculator example",
        scope="Make calc.add return a sum while preserving the tiny test suite.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes for test_calc.py"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="After one verifier failure, request deterministic fake teacher guidance and retry once.",
    )
    initial_writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")]
    revised_writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]

    executor = ToyWorkflowExecutor()
    report = executor.execute_with_teacher_retry(
        source_repo=project_root,
        contract=contract,
        initial_writes=initial_writes,
        teacher_guidance="Use addition, not multiplication, to satisfy the verifier.",
        revised_writes=revised_writes,
        project_name="provider-free-example",
    )
    promotion = executor.promote_verified_writes(
        source_repo=project_root,
        report=report,
        candidate_writes=revised_writes,
        target_branch="feiyue/m14-provider-free-example-smoke",
        commit_message="feat: promote provider-free example fix",
    )
    artifacts = WorkflowReportWriter(project_root).write(report=report, promotion=promotion)

    handoff_summary_path = artifacts.run_dir / "handoff-summary.md"
    handoff_summary_path.write_text(
        RunEvidenceLoader(project_root).render_handoff_summary(TASK_ID),
        encoding="utf-8",
    )

    export_result = export_static_runs_report_all(project_root, output_dir, bundle_path)
    return ProviderFreeExampleResult(
        task_id=TASK_ID,
        workflow_status=report.status.value,
        promotion_status=promotion.status.value,
        run_evidence_path=artifacts.run_evidence_json_path,
        handoff_summary_path=handoff_summary_path,
        report_index_path=export_result.report.index_path,
        manifest_path=export_result.report.manifest_path,
        bundle_path=export_result.bundle.bundle_path,
        extracted_dir=export_result.extracted_dir,
        initial_verify=export_result.initial_verification.valid,
        extracted_verify=export_result.extracted_verification.valid,
    )


def _init_toy_project(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"example root must be empty or absent: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (root / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add_returns_sum():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    _run(["git", "init"], cwd=root)
    _run(["git", "config", "user.email", "example@example.com"], cwd=root)
    _run(["git", "config", "user.name", "Feiyue Example"], cwd=root)
    _run(["git", "add", "calc.py", "test_calc.py"], cwd=root)
    _run(["git", "commit", "-m", "test: seed provider-free example"], cwd=root)


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m feiyue_core.examples.provider_free_smoke",
        description="Run the Feiyue provider-free example project smoke.",
    )
    parser.add_argument("--root", required=True, help="Empty or absent directory for the generated toy project")
    parser.add_argument("--out", required=True, help="Output directory for the static run report")
    parser.add_argument("--bundle", required=True, help="Output .zip bundle path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run_provider_free_example(root=args.root, out=args.out, bundle=args.bundle)
    print(f"task_id: {result.task_id}")
    print(f"workflow_status: {result.workflow_status}")
    print(f"promotion_status: {result.promotion_status}")
    print(f"run_evidence: {result.run_evidence_path}")
    print(f"handoff_summary: {result.handoff_summary_path}")
    print(f"manifest: {result.manifest_path}")
    print(f"bundle: {result.bundle_path}")
    print(f"initial_verify: {result.initial_verify}")
    print(f"extracted_verify: {result.extracted_verify}")
    if not result.initial_verify or not result.extracted_verify:
        return 1
    print("PROVIDER_FREE_EXAMPLE_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
