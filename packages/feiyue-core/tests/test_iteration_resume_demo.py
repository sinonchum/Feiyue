from __future__ import annotations

import json
import subprocess
import sys


def test_iteration_resume_demo_cli_outputs_clean_json(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.generation.iteration_resume_demo",
            "--root",
            str(tmp_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.lstrip().startswith("{")

    summary = json.loads(result.stdout)

    assert summary["event_count"] == 8
    assert summary["trace_path_exists"] is True
    assert summary["context"]["latest_candidate_id"] == "cand_demo_revised"
    assert summary["context"]["parent_candidate_id"] == "cand_demo_initial"
    assert summary["context"]["teacher_guidance_already_requested"] is True
    assert summary["context"]["next_safe_action"] == "promote verified candidate or run next acceptance gate"
    assert "# Iteration Fallback Resume Prompt" in summary["resume_prompt"]
    assert "## Do Not Repeat" in summary["resume_prompt"]
    assert "Do not request duplicate teacher guidance" in summary["resume_prompt"]


def test_iteration_resume_demo_function_writes_trace_and_resume_prompt(tmp_path) -> None:
    from feiyue_core.generation.iteration_resume_demo import run_demo

    summary = run_demo(tmp_path)

    assert summary["trace_path_exists"] is True
    assert summary["event_count"] == 8
    assert summary["context"]["candidate_lineage"] == ["cand_demo_initial", "cand_demo_revised"]
    assert summary["context"]["latest_verification_result_id"] == "verify_demo_pass"
    assert summary["resume_prompt"].count("## Next Safe Action") == 1
    assert (tmp_path / "iteration-resume-demo" / "iteration-trace.jsonl").exists()
