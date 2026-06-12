import subprocess

from feiyue_core.sandbox.worktree import WorktreeSandbox


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_repo(path):
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "value.txt").write_text("original\n", encoding="utf-8")
    _git(path, "add", "value.txt")
    _git(path, "commit", "-m", "initial")


def test_worktree_sandbox_creates_isolated_checkout(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    with WorktreeSandbox(repo) as sandbox:
        sandbox_file = sandbox.path / "value.txt"
        sandbox_file.write_text("changed in sandbox\n", encoding="utf-8")

        assert sandbox.path != repo
        assert sandbox_file.read_text(encoding="utf-8") == "changed in sandbox\n"
        assert (repo / "value.txt").read_text(encoding="utf-8") == "original\n"
        assert sandbox.head_sha == _git(repo, "rev-parse", "HEAD").stdout.strip()

    assert not sandbox.path.exists()
    assert _git(repo, "status", "--short").stdout == ""


def test_worktree_sandbox_can_keep_debug_directory(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    with WorktreeSandbox(repo, keep_on_exit=True) as sandbox:
        sandbox_path = sandbox.path
        assert sandbox_path.exists()

    assert sandbox_path.exists()
