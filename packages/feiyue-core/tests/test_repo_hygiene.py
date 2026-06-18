from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_repository_does_not_track_generated_hermes_artifacts() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    if not (repo_root / ".git").exists():
        pytest.skip("repository hygiene check requires a git checkout")

    completed = subprocess.run(
        ["git", "ls-files", ".hermes/**"],
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    tracked = [line for line in completed.stdout.splitlines() if line.strip()]
    assert tracked == [], "generated .hermes artifacts must stay out of git: " + ", ".join(tracked)
