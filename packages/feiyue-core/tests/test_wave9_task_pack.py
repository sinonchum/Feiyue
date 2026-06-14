from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from feiyue_core.providers.profile_runner import FakeProfileRunner
from feiyue_core.workflow.wave9_task_pack import (
    Wave9AssignmentExecutionReport,
    Wave9AuthorizationCheckStatus,
    Wave9ExecutionStatus,
    Wave9ExecutionReport,
    Wave9LocalPRPlanStatus,
    Wave9TaskAssignment,
    Wave9TaskPack,
    Wave9TaskPackAuthorization,
    Wave9TaskPackExecutor,
    create_wave9_local_pr_plan,
    approve_wave9_task_pack_execution,
    read_wave9_execution_evidence,
    read_wave9_local_pr_plan,
    read_wave9_task_pack_authorization,
    task_pack_hash,
    validate_wave9_task_pack_authorization,
    write_wave9_execution_evidence,
    write_wave9_task_pack,
    read_wave9_task_pack,
)


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = f"{source_path}{os.pathsep}{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else source_path
    return env


def _assignments() -> list[Wave9TaskAssignment]:
    return [
        Wave9TaskAssignment(
            assignment_id="impl",
            profile_id="feiyue-mid-deepseek-pro",
            role="implementation",
            objective="Implement the tiny feature in the allowed source file only.",
            allowed_files=["packages/feiyue-core/feiyue_core/workflow/wave9_marker.py"],
            verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
            max_profile_calls=1,
        ),
        Wave9TaskAssignment(
            assignment_id="tests",
            profile_id="feiyue-strong-gpt55",
            role="tests",
            objective="Add the matching focused regression test only.",
            allowed_files=["packages/feiyue-core/tests/test_wave9_marker.py"],
            verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
            max_profile_calls=1,
        ),
    ]


def test_wave9_task_pack_requires_non_empty_assignment_scope() -> None:
    with pytest.raises(ValidationError, match="allowed_files"):
        Wave9TaskAssignment(
            assignment_id="impl",
            profile_id="feiyue-mid-deepseek-pro",
            role="implementation",
            objective="Implement feature.",
            allowed_files=[],
            verifier_commands=["python -m pytest -q"],
            max_profile_calls=1,
        )


def test_wave9_task_pack_overlapping_scopes_require_reject_on_conflict() -> None:
    assignments = _assignments()
    assignments[1] = assignments[1].model_copy(
        update={"allowed_files": ["packages/feiyue-core/feiyue_core/workflow/wave9_marker.py"]}
    )

    with pytest.raises(ValidationError, match="overlapping assignment scopes require reject_on_conflict"):
        Wave9TaskPack(
            task_pack_id="wave9-2-task-pack",
            task_id="wave9.real-multi-worker.marker",
            title="Wave9 real multi-worker marker task",
            summary="Tiny scoped task pack for a future real multi-worker dry-run.",
            assignments=assignments,
            merge_strategy="ordered_overlay",
            verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
            review_criteria=["combined verifier passes", "source checkout remains clean"],
            dry_run_only=True,
            promotion_attempted=False,
            global_hermes_config_mutated=False,
            production_mutated=False,
            reason_codes=["wave9_task_pack_pre_execution_only"],
        )


def test_wave9_task_pack_persists_hashable_provider_free_evidence(tmp_path: Path) -> None:
    pack = Wave9TaskPack(
        task_pack_id="wave9-2-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only", "provider_calls_not_started"],
    )

    path = write_wave9_task_pack(pack, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    loaded = read_wave9_task_pack(tmp_path, "wave9-2-task-pack")

    assert path == tmp_path / ".hermes" / "wave9-task-packs" / "wave9-2-task-pack" / "task-pack.json"
    assert loaded.model_copy(update={"task_pack_hash": None}) == pack
    assert loaded.task_pack_hash == task_pack_hash(pack)
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False
    assert payload["global_hermes_config_mutated"] is False
    assert payload["production_mutated"] is False
    assert payload["provider_call_count"] == 0
    assert task_pack_hash(pack) == payload["task_pack_hash"]


def test_wave9_task_pack_cli_writes_provider_free_evidence(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "wave9-task-pack",
            "wave9-2-cli-task-pack",
            "--task-id",
            "wave9.real-multi-worker.marker",
            "--title",
            "Wave9 real multi-worker marker task",
            "--summary",
            "Tiny scoped task pack for a future real multi-worker dry-run.",
            "--assignment",
            "impl|feiyue-mid-deepseek-pro|implementation|Implement marker|packages/feiyue-core/feiyue_core/workflow/wave9_marker.py|python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q",
            "--assignment",
            "tests|feiyue-strong-gpt55|tests|Test marker|packages/feiyue-core/tests/test_wave9_marker.py|python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q",
            "--verifier-command",
            "python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q",
            "--review-criterion",
            "combined verifier passes",
            "--review-criterion",
            "source checkout remains clean",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )

    payload = json.loads(completed.stdout)
    assert payload["task_pack_id"] == "wave9-2-cli-task-pack"
    assert payload["task_pack_hash"]
    assert payload["provider_call_count"] == 0
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False
    assert payload["global_hermes_config_mutated"] is False
    assert payload["production_mutated"] is False
    assert (tmp_path / ".hermes" / "wave9-task-packs" / "wave9-2-cli-task-pack" / "task-pack.json").exists()



def test_wave9_3_authorization_blocks_missing_before_provider_calls(tmp_path: Path) -> None:
    pack = Wave9TaskPack(
        task_pack_id="wave9-3-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    write_wave9_task_pack(pack, tmp_path)

    check = validate_wave9_task_pack_authorization(pack=pack, authorization=None)

    assert check.status == Wave9AuthorizationCheckStatus.BLOCKED
    assert check.authorization_applies is False
    assert check.provider_call_count == 0
    assert check.dry_run_only is True
    assert check.promotion_attempted is False
    assert check.production_mutated is False
    assert "missing_wave9_task_pack_authorization" in check.reason_codes


def test_wave9_3_authorization_binds_exact_task_pack_hash_and_workers(tmp_path: Path) -> None:
    pack = Wave9TaskPack(
        task_pack_id="wave9-3-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    write_wave9_task_pack(pack, tmp_path)

    approval = approve_wave9_task_pack_execution(
        project_root=tmp_path,
        task_pack=pack,
        approval_id="wave9-3-approval",
        approved_by="test-suite",
        reason="Approve Wave9 dry-run execution only.",
        max_total_profile_calls=2,
    )
    loaded = read_wave9_task_pack_authorization(tmp_path, pack.task_pack_id)
    check = validate_wave9_task_pack_authorization(pack=pack, authorization=loaded)

    assert isinstance(approval, Wave9TaskPackAuthorization)
    assert loaded == approval
    assert approval.approved_action == "execute_wave9_real_multi_worker_dry_run"
    assert approval.task_pack_hash == task_pack_hash(pack)
    assert approval.worker_profile_ids == ["feiyue-mid-deepseek-pro", "feiyue-strong-gpt55"]
    assert approval.verifier_commands == pack.verifier_commands
    assert approval.merge_strategy == "reject_on_conflict"
    assert approval.dry_run_only is True
    assert check.status == Wave9AuthorizationCheckStatus.AUTHORIZED
    assert check.authorization_applies is True
    assert check.provider_call_count == 0
    assert check.reason_codes == ["wave9_task_pack_authorization_applies", "provider_calls_not_started"]


def test_wave9_3_authorization_mismatch_blocks_before_provider_calls(tmp_path: Path) -> None:
    pack = Wave9TaskPack(
        task_pack_id="wave9-3-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    authorization = Wave9TaskPackAuthorization(
        approval_id="wave9-3-wrong",
        approved_by="test-suite",
        task_pack_id=pack.task_pack_id,
        task_id=pack.task_id,
        approved_action="execute_wave9_real_multi_worker_dry_run",
        task_pack_hash="wrong-hash",
        worker_profile_ids=["feiyue-mid-deepseek-pro", "feiyue-strong-gpt55"],
        verifier_commands=pack.verifier_commands,
        merge_strategy=pack.merge_strategy,
        dry_run_only=True,
        max_total_profile_calls=2,
        reason="Wrong hash should block.",
    )

    check = validate_wave9_task_pack_authorization(pack=pack, authorization=authorization)

    assert check.status == Wave9AuthorizationCheckStatus.BLOCKED
    assert check.authorization_applies is False
    assert check.provider_call_count == 0
    assert "task_pack_hash_mismatch" in check.reason_codes


def test_wave9_3_cli_approves_task_pack_execution_without_provider_calls(tmp_path: Path) -> None:
    pack = Wave9TaskPack(
        task_pack_id="wave9-3-cli-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    write_wave9_task_pack(pack, tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "approve-wave9-real-multi-worker-run",
            "--task-pack-id",
            "wave9-3-cli-task-pack",
            "--approved-by",
            "test-suite",
            "--approval-id",
            "wave9-3-cli-approval",
            "--reason",
            "Approve Wave9 real multi-worker dry-run only.",
            "--max-total-profile-calls",
            "2",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )

    payload = json.loads(completed.stdout)
    assert payload["approval_id"] == "wave9-3-cli-approval"
    assert payload["approved_action"] == "execute_wave9_real_multi_worker_dry_run"
    assert payload["task_pack_hash"] == task_pack_hash(pack)
    assert payload["provider_call_count"] == 0
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False
    assert payload["production_mutated"] is False
    assert (tmp_path / ".hermes" / "wave9-task-packs" / "wave9-3-cli-task-pack" / "authorization.json").exists()



def _source_repo(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "packages" / "feiyue-core" / "feiyue_core" / "workflow").mkdir(parents=True)
    (source / "packages" / "feiyue-core" / "tests").mkdir(parents=True)
    (source / "packages" / "feiyue-core" / "feiyue_core" / "__init__.py").write_text("", encoding="utf-8")
    (source / "packages" / "feiyue-core" / "feiyue_core" / "workflow" / "__init__.py").write_text("", encoding="utf-8")
    (source / "packages" / "feiyue-core" / "feiyue_core" / "workflow" / "wave9_marker.py").write_text(
        "def wave9_marker():\n    return 'pending'\n",
        encoding="utf-8",
    )
    (source / "packages" / "feiyue-core" / "tests" / "test_wave9_marker.py").write_text(
        "from feiyue_core.workflow.wave9_marker import wave9_marker\n\n"
        "def test_wave9_marker():\n    assert wave9_marker() == 'verified'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=source, check=True, capture_output=True, text=True)
    return source


def test_wave9_4_executor_blocks_without_authorization_before_provider_calls(tmp_path: Path) -> None:
    source = _source_repo(tmp_path)
    pack = Wave9TaskPack(
        task_pack_id="wave9-4-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["PYTHONPATH=packages/feiyue-core python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )

    report = Wave9TaskPackExecutor(profile_runner=FakeProfileRunner({})).run(
        project_root=tmp_path,
        source_repo=source,
        project_name="Feiyue",
        task_pack=pack,
        authorization=None,
        run_id="wave9-4-blocked",
    )

    assert report.status == Wave9ExecutionStatus.BLOCKED
    assert report.provider_call_count == 0
    assert report.authorization_applies is False
    assert "missing_wave9_task_pack_authorization" in report.reason_codes
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.external_pr_created is False
    assert report.merge_performed is False
    assert report.deploy_performed is False
    assert report.global_hermes_config_mutated is False
    assert report.production_mutated is False


def test_wave9_4_executor_runs_authorized_dry_run_in_sandbox(tmp_path: Path) -> None:
    source = _source_repo(tmp_path)
    pack = Wave9TaskPack(
        task_pack_id="wave9-4-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["PYTHONPATH=packages/feiyue-core python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    write_wave9_task_pack(pack, tmp_path)
    authorization = approve_wave9_task_pack_execution(
        project_root=tmp_path,
        task_pack=pack,
        approval_id="wave9-4-approval",
        approved_by="test-suite",
        reason="Authorize Wave9 dry-run execution only.",
        max_total_profile_calls=2,
    )
    responses = {
        "feiyue-mid-deepseek-pro": json.dumps({
            "writes": [
                {
                    "path": "packages/feiyue-core/feiyue_core/workflow/wave9_marker.py",
                    "content": "def wave9_marker():\n    return 'verified'\n",
                }
            ]
        }),
        "feiyue-strong-gpt55": json.dumps({
            "writes": [
                {
                    "path": "packages/feiyue-core/tests/test_wave9_marker.py",
                    "content": "from feiyue_core.workflow.wave9_marker import wave9_marker\n\ndef test_wave9_marker():\n    assert wave9_marker() == 'verified'\n",
                }
            ]
        }),
    }

    report = Wave9TaskPackExecutor(profile_runner=FakeProfileRunner(responses)).run(
        project_root=tmp_path,
        source_repo=source,
        project_name="Feiyue",
        task_pack=pack,
        authorization=authorization,
        run_id="wave9-4-verified",
    )
    loaded = read_wave9_execution_evidence(tmp_path, "wave9-4-verified")

    assert report.status == Wave9ExecutionStatus.VERIFIED
    assert loaded == report
    assert report.authorization_applies is True
    assert report.approval_id == "wave9-4-approval"
    assert report.provider_call_count == 2
    assert report.conflict_files == []
    assert all(item["exit_code"] == 0 for item in report.verifier_outputs)
    assert [item.status for item in report.assignment_reports] == ["candidate_ready", "candidate_ready"]
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.external_pr_created is False
    assert report.merge_performed is False
    assert report.deploy_performed is False
    assert report.global_hermes_config_mutated is False
    assert report.production_mutated is False
    assert report.source_repo_clean is True
    assert (source / "packages" / "feiyue-core" / "feiyue_core" / "workflow" / "wave9_marker.py").read_text(encoding="utf-8").strip().endswith("'pending'")


def test_wave9_4_cli_runs_authorized_fake_dry_run(tmp_path: Path) -> None:
    source = _source_repo(tmp_path)
    pack = Wave9TaskPack(
        task_pack_id="wave9-4-cli-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["PYTHONPATH=packages/feiyue-core python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    write_wave9_task_pack(pack, tmp_path)
    approve_wave9_task_pack_execution(
        project_root=tmp_path,
        task_pack=pack,
        approval_id="wave9-4-cli-approval",
        approved_by="test-suite",
        reason="Authorize Wave9 dry-run execution only.",
        max_total_profile_calls=2,
    )
    impl_response = json.dumps({"writes": [{"path": "packages/feiyue-core/feiyue_core/workflow/wave9_marker.py", "content": "def wave9_marker():\n    return 'verified'\n"}]})
    test_response = json.dumps({"writes": [{"path": "packages/feiyue-core/tests/test_wave9_marker.py", "content": "from feiyue_core.workflow.wave9_marker import wave9_marker\n\ndef test_wave9_marker():\n    assert wave9_marker() == 'verified'\n"}]})

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "run-approved-wave9-real-multi-worker-dry-run",
            "--task-pack-id",
            "wave9-4-cli-task-pack",
            "--run-id",
            "wave9-4-cli-run",
            "--source-repo",
            str(source),
            "--project-name",
            "Feiyue",
            "--profile-runner",
            "fake",
            "--fake-response",
            f"feiyue-mid-deepseek-pro={impl_response}",
            "--fake-response",
            f"feiyue-strong-gpt55={test_response}",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "verified"
    assert payload["provider_call_count"] == 2
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False
    assert payload["external_pr_created"] is False
    assert payload["merge_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["production_mutated"] is False
    assert (tmp_path / ".hermes" / "wave9-real-multi-worker-runs" / "wave9-4-cli-run" / "evidence.json").exists()



def _verified_wave9_report(run_id: str = "wave9-5-source-run"):
    return Wave9TaskPackExecutor(profile_runner=FakeProfileRunner({
        "feiyue-mid-deepseek-pro": json.dumps({
            "writes": [{"path": "packages/feiyue-core/feiyue_core/workflow/wave9_marker.py", "content": "def wave9_marker():\n    return 'verified'\n"}]
        }),
        "feiyue-strong-gpt55": json.dumps({
            "writes": [{"path": "packages/feiyue-core/tests/test_wave9_marker.py", "content": "from feiyue_core.workflow.wave9_marker import wave9_marker\n\ndef test_wave9_marker():\n    assert wave9_marker() == 'verified'\n"}]
        }),
    }))


def test_wave9_5_local_pr_plan_requires_verified_execution(tmp_path: Path) -> None:
    pack = Wave9TaskPack(
        task_pack_id="wave9-5-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    report = Wave9ExecutionReport(
        run_id="wave9-5-failed-run",
        task_pack_id=pack.task_pack_id,
        task_id=pack.task_id,
        status=Wave9ExecutionStatus.FAILED,
        authorization_applies=True,
        provider_call_count=2,
        reason_codes=["combined_verifier_failed"],
        dry_run_only=True,
        promotion_attempted=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        source_repo_clean=True,
    )

    plan = create_wave9_local_pr_plan(
        project_root=tmp_path,
        execution_report=report,
        plan_id="wave9-5-local-pr-plan",
        target_branch="wave9/real-multi-worker-marker",
        title="Wave9 marker local PR plan",
    )

    assert plan.status == Wave9LocalPRPlanStatus.BLOCKED
    assert plan.provider_call_count == 0
    assert plan.external_pr_created is False
    assert plan.merge_performed is False
    assert plan.deploy_performed is False
    assert plan.production_mutated is False
    assert "execution_not_verified" in plan.reason_codes


def test_wave9_5_local_pr_plan_from_verified_execution_is_local_only(tmp_path: Path) -> None:
    source = _source_repo(tmp_path)
    pack = Wave9TaskPack(
        task_pack_id="wave9-5-task-pack",
        task_id="wave9.real-multi-worker.marker",
        title="Wave9 real multi-worker marker task",
        summary="Tiny scoped task pack for a future real multi-worker dry-run.",
        assignments=_assignments(),
        merge_strategy="reject_on_conflict",
        verifier_commands=["PYTHONPATH=packages/feiyue-core python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q"],
        review_criteria=["combined verifier passes", "source checkout remains clean"],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_pre_execution_only"],
    )
    authorization = approve_wave9_task_pack_execution(
        project_root=tmp_path,
        task_pack=pack,
        approval_id="wave9-5-approval",
        approved_by="test-suite",
        reason="Authorize Wave9 dry-run execution only.",
        max_total_profile_calls=2,
    )
    report = Wave9TaskPackExecutor(profile_runner=FakeProfileRunner({
        "feiyue-mid-deepseek-pro": json.dumps({"writes": [{"path": "packages/feiyue-core/feiyue_core/workflow/wave9_marker.py", "content": "def wave9_marker():\n    return 'verified'\n"}]}),
        "feiyue-strong-gpt55": json.dumps({"writes": [{"path": "packages/feiyue-core/tests/test_wave9_marker.py", "content": "from feiyue_core.workflow.wave9_marker import wave9_marker\n\ndef test_wave9_marker():\n    assert wave9_marker() == 'verified'\n"}]}),
    })).run(
        project_root=tmp_path,
        source_repo=source,
        project_name="Feiyue",
        task_pack=pack,
        authorization=authorization,
        run_id="wave9-5-source-run",
    )

    plan = create_wave9_local_pr_plan(
        project_root=tmp_path,
        execution_report=report,
        plan_id="wave9-5-local-pr-plan",
        target_branch="wave9/real-multi-worker-marker",
        title="Wave9 marker local PR plan",
    )
    loaded = read_wave9_local_pr_plan(tmp_path, "wave9-5-local-pr-plan")

    assert report.status == Wave9ExecutionStatus.VERIFIED
    assert loaded == plan
    assert plan.status == Wave9LocalPRPlanStatus.PLANNED
    assert plan.execution_run_id == "wave9-5-source-run"
    assert plan.task_pack_id == "wave9-5-task-pack"
    assert plan.target_branch == "wave9/real-multi-worker-marker"
    assert plan.provider_call_count == 0
    assert plan.external_pr_created is False
    assert plan.merge_performed is False
    assert plan.deploy_performed is False
    assert plan.production_mutated is False
    assert plan.dry_run_only is True
    assert plan.promotion_attempted is False
    assert plan.source_repo_clean is True
    assert sorted(plan.changed_files) == [
        "packages/feiyue-core/feiyue_core/workflow/wave9_marker.py",
        "packages/feiyue-core/tests/test_wave9_marker.py",
    ]
    assert "local_pr_plan_only" in plan.reason_codes


def test_wave9_5_cli_creates_local_pr_plan_from_execution_evidence(tmp_path: Path) -> None:
    report = Wave9ExecutionReport(
        run_id="wave9-5-cli-source-run",
        task_pack_id="wave9-5-cli-task-pack",
        task_id="wave9.real-multi-worker.marker",
        status=Wave9ExecutionStatus.VERIFIED,
        authorization_applies=True,
        assignment_reports=[
            Wave9AssignmentExecutionReport(assignment_id="impl", profile_id="feiyue-mid-deepseek-pro", role="implementation", status="candidate_ready", candidate_files=["packages/feiyue-core/feiyue_core/workflow/wave9_marker.py"], allowed_scope=True, exit_code=0, reason_codes=["candidate_writes_scope_ok"]),
            Wave9AssignmentExecutionReport(assignment_id="tests", profile_id="feiyue-strong-gpt55", role="tests", status="candidate_ready", candidate_files=["packages/feiyue-core/tests/test_wave9_marker.py"], allowed_scope=True, exit_code=0, reason_codes=["candidate_writes_scope_ok"]),
        ],
        provider_call_count=2,
        reason_codes=["combined_verifier_passed"],
        conflict_files=[],
        verifier_outputs=[{"command": "python -m pytest packages/feiyue-core/tests/test_wave9_marker.py -q", "exit_code": 0, "stdout": "1 passed", "stderr": ""}],
        dry_run_only=True,
        promotion_attempted=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        source_repo_clean=True,
    )
    write_wave9_execution_evidence(report, tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "wave9-local-pr-plan",
            "--execution-run-id",
            "wave9-5-cli-source-run",
            "--plan-id",
            "wave9-5-cli-local-pr-plan",
            "--target-branch",
            "wave9/real-multi-worker-marker",
            "--title",
            "Wave9 marker local PR plan",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "planned"
    assert payload["provider_call_count"] == 0
    assert payload["external_pr_created"] is False
    assert payload["merge_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["production_mutated"] is False
    assert (tmp_path / ".hermes" / "wave9-local-pr-plans" / "wave9-5-cli-local-pr-plan" / "pr-plan.json").exists()
