import hashlib
import subprocess

from feiyue_core.runtime import SideEffectInspector, SideEffectStatus


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def test_file_hash_check_confirms_expected_content(tmp_path) -> None:
    target = tmp_path / "artifact.txt"
    target.write_text("stable output\n", encoding="utf-8")

    result = SideEffectInspector().check_file_hash(target, expected_sha256=_sha256("stable output\n"))

    assert result.status == SideEffectStatus.CONFIRMED
    assert result.subject == str(target)
    assert result.observed["exists"] is True


def test_file_hash_check_requires_inspection_when_hash_differs(tmp_path) -> None:
    target = tmp_path / "artifact.txt"
    target.write_text("changed output\n", encoding="utf-8")

    result = SideEffectInspector().check_file_hash(target, expected_sha256=_sha256("stable output\n"))

    assert result.status == SideEffectStatus.NEEDS_INSPECTION
    assert result.reason == "file hash mismatch"


def test_artifact_check_marks_missing_as_needs_inspection(tmp_path) -> None:
    target = tmp_path / "missing.jsonl"

    result = SideEffectInspector().check_artifact_exists(target)

    assert result.status == SideEffectStatus.NEEDS_INSPECTION
    assert result.reason == "artifact missing"


def test_git_ref_check_confirms_expected_head(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    result = SideEffectInspector().check_git_ref(repo, "HEAD", expected_sha=head)

    assert result.status == SideEffectStatus.CONFIRMED
    assert result.observed["sha"] == head


def test_git_ref_check_marks_mismatch_unsafe_to_repeat(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    result = SideEffectInspector().check_git_ref(repo, "HEAD", expected_sha="deadbeef")

    assert result.status == SideEffectStatus.UNSAFE_TO_REPEAT
    assert result.reason == "git ref mismatch"


def _make_local_and_bare_remote(tmp_path):
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "README.md").write_text("hello\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "initial")
    head = _git(source, "rev-parse", "HEAD").stdout.strip()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    _git(source, "remote", "add", "origin", str(remote))
    _git(source, "push", "origin", "HEAD:refs/heads/main")
    return source, remote, head


def test_git_remote_ref_check_confirms_expected_remote_head(tmp_path) -> None:
    _source, remote, head = _make_local_and_bare_remote(tmp_path)

    result = SideEffectInspector().check_git_remote_ref(str(remote), "refs/heads/main", expected_sha=head)

    assert result.status == SideEffectStatus.CONFIRMED
    assert result.reason == "git remote ref matches"
    assert result.observed["sha"] == head


def test_git_remote_ref_check_marks_mismatch_unsafe_to_repeat(tmp_path) -> None:
    _source, remote, _head = _make_local_and_bare_remote(tmp_path)

    result = SideEffectInspector().check_git_remote_ref(str(remote), "refs/heads/main", expected_sha="deadbeef")

    assert result.status == SideEffectStatus.UNSAFE_TO_REPEAT
    assert result.reason == "git remote ref mismatch"


def test_inspect_dispatches_git_remote_ref_specs(tmp_path) -> None:
    _source, remote, head = _make_local_and_bare_remote(tmp_path)

    result = SideEffectInspector().inspect(
        {"type": "git_remote_ref", "remote_url": str(remote), "ref": "refs/heads/main", "expected_sha": head}
    )

    assert result.status == SideEffectStatus.CONFIRMED


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_github_ref_check_confirms_expected_sha_from_api(monkeypatch) -> None:
    def fake_run(args, text, capture_output, check):
        assert args == ["gh", "api", "repos/sinonchum/Feiyue/git/ref/heads/main", "--jq", ".object.sha"]
        return _Completed(stdout="abc123\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SideEffectInspector().check_github_ref("sinonchum/Feiyue", "refs/heads/main", expected_sha="abc123")

    assert result.status == SideEffectStatus.CONFIRMED
    assert result.reason == "github ref matches"
    assert result.observed["sha"] == "abc123"


def test_github_ref_check_marks_mismatch_unsafe_to_repeat(monkeypatch) -> None:
    def fake_run(args, text, capture_output, check):
        return _Completed(stdout="def456\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SideEffectInspector().check_github_ref("sinonchum/Feiyue", "refs/heads/main", expected_sha="abc123")

    assert result.status == SideEffectStatus.UNSAFE_TO_REPEAT
    assert result.reason == "github ref mismatch"


def test_inspect_dispatches_github_ref_specs(monkeypatch) -> None:
    def fake_run(args, text, capture_output, check):
        return _Completed(stdout="abc123\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SideEffectInspector().inspect(
        {"type": "github_ref", "repo": "sinonchum/Feiyue", "ref": "refs/heads/main", "expected_sha": "abc123"}
    )

    assert result.status == SideEffectStatus.CONFIRMED
