from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import cog_bump
from tests.conftest import git


def read_outputs(path: Path) -> dict[str, str]:
    """Parse the ``name<<DELIM ... DELIM`` blocks GitHub Actions uses."""
    out: dict[str, str] = {}
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        name, _, delim = lines[i].partition("<<")
        i += 1
        body: list[str] = []
        while i < len(lines) and lines[i] != delim:
            body.append(lines[i])
            i += 1
        i += 1
        out[name] = "\n".join(body)
    return out


@pytest.fixture
def github_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "gh_output"
    path.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return path


@pytest.mark.parametrize(
    ("bump", "expected"),
    [
        ("auto", "--auto"),
        ("patch", "--patch"),
        ("minor", "--minor"),
        ("major", "--major"),
    ],
)
def test_bump_arg(bump: str, expected: str) -> None:
    assert cog_bump.bump_arg(bump) == expected


def test_nothing_to_release(
    repo: Path, fake_cog: Path, github_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.delenv("COG_FAKE_TAGS", raising=False)

    assert cog_bump.main() == 0

    outputs = read_outputs(github_output)
    assert outputs == {"tag": "", "tags": ""}


def test_single_tag(
    repo: Path, fake_cog: Path, github_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("COG_FAKE_TAGS", "v1.3.0")

    assert cog_bump.main() == 0

    outputs = read_outputs(github_output)
    assert outputs["tag"] == "v1.3.0"
    assert outputs["tags"] == "v1.3.0"


def test_monorepo_multiple_tags(
    repo: Path, fake_cog: Path, github_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("COG_FAKE_TAGS", "repokit-v0.3.0,asyncgh-v0.6.0")

    assert cog_bump.main() == 0

    outputs = read_outputs(github_output)
    assert outputs["tags"].splitlines() == ["asyncgh-v0.6.0", "repokit-v0.3.0"]
    assert outputs["tag"] == "asyncgh-v0.6.0"


def test_preexisting_tags_are_ignored(
    repo: Path, fake_cog: Path, github_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git("tag", "asyncgh-v0.5.1", cwd=repo)
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("COG_FAKE_TAGS", "asyncgh-v0.6.0")

    assert cog_bump.main() == 0

    assert read_outputs(github_output)["tags"] == "asyncgh-v0.6.0"


def test_config_is_passed_through(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = tmp_path / "argv"
    monkeypatch.setenv("COG_FAKE_ARGV", str(argv))
    monkeypatch.setenv("COG_FAKE_TAGS", "v1.0.0")
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("CONFIG", "sub/cog.toml")

    cog_bump.main()

    assert argv.read_text().split() == ["--config", "sub/cog.toml", "bump", "--auto"]


def test_no_config_uses_bundled(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = tmp_path / "argv"
    monkeypatch.setenv("COG_FAKE_ARGV", str(argv))
    monkeypatch.setenv("COG_FAKE_TAGS", "v1.0.0")
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.delenv("CONFIG", raising=False)

    cog_bump.main()

    assert argv.read_text().split() == [
        "--config",
        cog_bump.bundled_config(),
        "bump",
        "--auto",
    ]


def test_bundled_config_points_at_repo_cog_toml() -> None:
    assert cog_bump.bundled_config().endswith("/cog.toml")
    assert Path(cog_bump.bundled_config()).is_file()


def test_push_sends_every_new_tag(
    repo: Path,
    bare_remote: Path,
    fake_cog: Path,
    github_output: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUSH", "true")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("COG_FAKE_TAGS", "asyncgh-v0.6.0,repokit-v0.3.0")

    assert cog_bump.main() == 0

    pushed = subprocess.run(
        ["git", "tag"], cwd=bare_remote, check=True, text=True, capture_output=True
    ).stdout.split()
    assert sorted(pushed) == ["asyncgh-v0.6.0", "repokit-v0.3.0"]


def test_push_skipped_when_disabled(
    repo: Path,
    bare_remote: Path,
    fake_cog: Path,
    github_output: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("COG_FAKE_TAGS", "v9.9.9")

    assert cog_bump.main() == 0

    pushed = subprocess.run(
        ["git", "tag"], cwd=bare_remote, check=True, text=True, capture_output=True
    ).stdout
    assert "v9.9.9" not in pushed
