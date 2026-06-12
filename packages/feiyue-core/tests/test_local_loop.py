import subprocess

from feiyue_core.orchestrator.local_loop import LocalLoop
from feiyue_core.schemas import Candidate, CandidateStatus, TaskSpec, TaskStatus, TaskType


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_toy_repo(path):
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "math_tools.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    tests = path / "tests"
    tests.mkdir()
    (tests / "test_math_tools.py").write_text(
        "from math_tools import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")


def test_local_loop_applies_patch_and_records_trace_without_dirtying_repo(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_toy_repo(repo)
    trace_path = tmp_path / "trace" / "events.jsonl"
    task = TaskSpec(
        id="task_001",
        title="Fix add",
        type=TaskType.CODE,
        status=TaskStatus.CREATED,
        goal="Make pytest pass",
        acceptance_criteria=["pytest passes"],
    )
    candidate = Candidate(
        id="cand_001",
        task_id="task_001",
        status=CandidateStatus.GENERATED,
        summary="Fix add implementation",
        metadata={"file_writes": {"math_tools.py": "def add(a, b):\n    return a + b\n"}},
    )

    result = LocalLoop(trace_path=trace_path).run(repo, task, candidate)

    assert result.verification.passed is True
    assert result.execution.exit_code == 0
    assert "pytest" in result.execution.command
    assert result.candidate.status == CandidateStatus.VERIFIED
    assert trace_path.exists()
    assert "tool_operation_finished" in trace_path.read_text(encoding="utf-8")
    assert (repo / "math_tools.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    assert _git(repo, "status", "--short").stdout == ""
