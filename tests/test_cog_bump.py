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
    assert outputs == {"tag": "", "tags": "", "notes": ""}


def test_single_tag(
    repo: Path, fake_cog: Path, github_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("COG_FAKE_TAGS", "v1.3.0")
    monkeypatch.setenv("COG_FAKE_CHANGELOG", "## v1.3.0\n- feat: thing\n")

    assert cog_bump.main() == 0

    outputs = read_outputs(github_output)
    assert outputs["tag"] == "v1.3.0"
    assert outputs["tags"] == "v1.3.0"
    assert outputs["notes"] == "## v1.3.0\n- feat: thing\n"


def test_changelog_uses_first_tag_and_config(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = tmp_path / "changelog_argv"
    monkeypatch.setenv("COG_FAKE_CHANGELOG_ARGV", str(argv))
    monkeypatch.setenv("COG_FAKE_TAGS", "repokit-v0.3.0,asyncgh-v0.6.0")
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("CONFIG", "sub/cog.toml")

    assert cog_bump.main() == 0

    assert argv.read_text().split() == [
        "--config",
        "sub/cog.toml",
        "changelog",
        "--at",
        "asyncgh-v0.6.0",
    ]


def test_monorepo_changelog_uses_package_template(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cocogitto's default monorepo template fails to render with `--at`
    # ("Variable `packages` not found"), which would crash after tagging.
    config = tmp_path / "cog.toml"
    config.write_text('[monorepo.packages]\nrepokit = { path = "repokit" }\n')
    argv = tmp_path / "changelog_argv"
    monkeypatch.setenv("COG_FAKE_CHANGELOG_ARGV", str(argv))
    monkeypatch.setenv("COG_FAKE_CHANGELOG", "#### Bug Fixes")
    monkeypatch.setenv("COG_FAKE_TAGS", "repokit-v0.3.1")
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("CONFIG", str(config))

    assert cog_bump.main() == 0

    assert argv.read_text().split()[-4:] == [
        "--at",
        "repokit-v0.3.1",
        "-t",
        "package_default",
    ]
    assert read_outputs(github_output)["notes"] == "#### Bug Fixes"


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
    git("tag", "v0.9.0", cwd=repo)
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
    git("tag", "v0.9.0", cwd=repo)
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


def test_check_failure_blocks_release(
    repo: Path, fake_cog: Path, github_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("COG_FAKE_CHECK_EXIT", "1")
    monkeypatch.setenv("COG_FAKE_TAGS", "v1.0.0")

    assert cog_bump.main() == 1

    assert cog_bump.git_tags() == set()
    assert github_output.read_text() == ""


def test_check_passes_config_through(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git("tag", "v0.9.0", cwd=repo)
    check_argv = tmp_path / "check_argv"
    monkeypatch.setenv("COG_FAKE_CHECK_ARGV", str(check_argv))
    monkeypatch.setenv("COG_FAKE_TAGS", "v1.0.0")
    monkeypatch.setenv("PUSH", "false")
    monkeypatch.setenv("CONFIG", "sub/cog.toml")

    assert cog_bump.main() == 0

    assert check_argv.read_text().split() == [
        "--config",
        "sub/cog.toml",
        "check",
        "v0.9.0..HEAD",
    ]


def test_check_range_starts_at_package_tag(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A monorepo has only `<package>-v<version>` tags, which `cog check
    # --from-latest-tag` doesn't count: it fails with "unable to get any tag".
    git("tag", "asyncgh-v0.5.0", cwd=repo)
    check_argv = tmp_path / "check_argv"
    monkeypatch.setenv("COG_FAKE_CHECK_ARGV", str(check_argv))
    monkeypatch.setenv("PUSH", "false")

    assert cog_bump.main() == 0

    assert check_argv.read_text().split()[-1] == "asyncgh-v0.5.0..HEAD"


def test_check_covers_full_history_when_untagged(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `cog check --from-latest-tag` fails with "unable to get any tag" in a repo
    # with no tags, which would block a new repo's first release.
    check_argv = tmp_path / "check_argv"
    monkeypatch.setenv("COG_FAKE_CHECK_ARGV", str(check_argv))
    monkeypatch.setenv("COG_FAKE_TAGS", "v0.1.0")
    monkeypatch.setenv("PUSH", "false")

    assert cog_bump.main() == 0

    assert check_argv.read_text().split() == [
        "--config",
        cog_bump.bundled_config(),
        "check",
    ]
    assert read_outputs(github_output)["tag"] == "v0.1.0"


def _bump_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    argv = tmp_path / "argv"
    monkeypatch.setenv("COG_FAKE_ARGV", str(argv))
    monkeypatch.setenv("COG_FAKE_TAGS", "v0.1.0")
    monkeypatch.setenv("PUSH", "false")
    return argv


def test_first_release_is_forced_to_0_1_0(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # From 0.0.0, --auto would give 0.0.1 for fix-only history and nothing at
    # all for chore-only history; a first release is always 0.1.0 instead.
    argv = _bump_argv(tmp_path, monkeypatch)

    assert cog_bump.main() == 0

    assert argv.read_text().split()[-2:] == ["bump", "--minor"]


def test_explicit_bump_is_kept_on_first_release(
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = _bump_argv(tmp_path, monkeypatch)
    monkeypatch.setenv("BUMP", "major")

    cog_bump.main()

    assert argv.read_text().split()[-2:] == ["bump", "--major"]


@pytest.mark.parametrize("table", ["packages", "monorepo.packages"])
def test_monorepo_first_release_stays_auto(
    table: str,
    repo: Path,
    fake_cog: Path,
    github_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A monorepo config ([packages] before cocogitto 7, [monorepo.packages]
    # since) tags each package on its own; --auto decides which.
    config = tmp_path / "cog.toml"
    config.write_text(f'[{table}]\nasyncgh = {{ path = "asyncgh" }}\n')
    argv = _bump_argv(tmp_path, monkeypatch)
    monkeypatch.setenv("CONFIG", str(config))

    cog_bump.main()

    assert argv.read_text().split()[-2:] == ["bump", "--auto"]


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
