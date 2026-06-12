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
