"""Fixtures: a throwaway git repo and a stub `cog` on PATH."""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git("init", "-q", "-b", "main", cwd=root)
    git("config", "user.email", "t@example.com", cwd=root)
    git("config", "user.name", "tester", cwd=root)
    (root / "f").write_text("x\n")
    git("add", "-A", cwd=root)
    git("commit", "-qm", "init", cwd=root)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def bare_remote(tmp_path: Path, repo: Path) -> Path:
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", str(remote), cwd=repo)
    git("remote", "add", "origin", str(remote), cwd=repo)
    git("push", "-q", "origin", "main", cwd=repo)
    return remote


@pytest.fixture
def fake_cog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `cog` stub. Creates the tags in ``COG_FAKE_TAGS`` (comma-separated) and
    records its argv to ``COG_FAKE_ARGV``; exits non-zero when it made no tag,
    like cocogitto does when there is nothing to release."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    cog = bindir / "cog"
    cog.write_text(
        textwrap.dedent("""\
        #!/usr/bin/env bash
        set -e
        [ -n "${COG_FAKE_ARGV:-}" ] && printf '%s ' "$@" > "$COG_FAKE_ARGV"
        made=0
        IFS=',' read -ra tags <<< "${COG_FAKE_TAGS:-}"
        for t in "${tags[@]}"; do
          if [ -n "$t" ]; then git tag "$t"; made=1; fi
        done
        [ "$made" = 1 ] || exit 1
        """)
    )
    cog.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return cog
