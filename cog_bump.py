#!/usr/bin/env python3
"""Bump versions with cocogitto (tag-only), then emit and push the new tags.

Driven entirely by environment variables so the composite action can call it
without argument plumbing:

    BUMP        auto | patch | minor | major        (default: auto)
    CONFIG      path to a cog.toml to use            (default: bundled cog.toml)
    PUSH        "true" to push the new tags          (default: "true")
    GH_TOKEN    token for the tag push               (default: unset)

cocogitto is run with ``--config`` so a monorepo repo can supply its own
``[monorepo.packages]`` table (``[packages]`` before cocogitto 7); ``cog bump --auto`` then tags every package whose files
changed. Any tags that appear are reported (``tag`` = first, ``tags`` = all,
newline-separated) via ``$GITHUB_OUTPUT`` and pushed.

Before bumping, ``cog check <latest-tag>..HEAD`` validates every commit since
the latest tag against Conventional Commits (the whole history when the repo
has no tag yet).

A repo's first release (no tags yet) is always 0.1.0 with ``BUMP=auto``,
except for a monorepo config, which keeps ``--auto`` per package. A commit that doesn't parse
would otherwise just be silently skipped by ``cog bump`` (dropped from the
version calculation without an error), which can under-bump a release, so
this fails loudly instead: exit 1, no tags, nothing pushed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

_OUTPUT_DELIMITER = "COG_BUMP_EOF"


def git_tags() -> set[str]:
    out = subprocess.run(
        ["git", "tag"], check=True, text=True, capture_output=True
    ).stdout
    return {line for line in out.splitlines() if line}


def latest_tag() -> str:
    return subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def bump_arg(bump: str) -> str:
    return "--auto" if bump == "auto" else f"--{bump}"


def is_monorepo(config: str) -> bool:
    try:
        with Path(resolved_config(config)).open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return "packages" in data or "packages" in data.get("monorepo", {})


def effective_bump_arg(bump: str, config: str, first_release: bool) -> str:
    # From 0.0.0, --auto gives 0.0.1 for fix-only history and no release at
    # all for chore-only history, so a repo's first release is pinned to 0.1.0.
    # A monorepo keeps --auto: it tags each package on its own.
    if bump == "auto" and first_release and not is_monorepo(config):
        return "--minor"
    return bump_arg(bump)


def bundled_config() -> str:
    return str(Path(__file__).with_name("cog.toml"))


def resolved_config(config: str) -> str:
    return config or bundled_config()


def run_check(config: str) -> bool:
    cmd = ["cog", "--config", resolved_config(config), "check"]
    # An explicit range rather than `--from-latest-tag`, which ignores monorepo
    # package tags. With no tag yet, a repo's first release checks its whole
    # history instead.
    if git_tags():
        cmd.append(f"{latest_tag()}..HEAD")
        scope = "since latest tag"
    else:
        scope = "in full history (no tags yet)"
    print(f"cog-bump: checking commit messages {scope}: {' '.join(cmd)}")
    ok = subprocess.run(cmd, check=False).returncode == 0
    print(
        "cog-bump: commit messages OK"
        if ok
        else "cog-bump: invalid commit message(s) found (see above)"
    )
    return ok


def run_cog(config: str, arg: str) -> None:
    cmd = ["cog", "--config", resolved_config(config), "bump", arg]
    print(f"cog-bump: running: {' '.join(cmd)}")
    # cocogitto exits non-zero when there is nothing to release; the tag diff,
    # not the exit code, tells us what actually happened.
    subprocess.run(cmd, check=False)


def changelog(config: str, tag: str) -> str:
    cmd = ["cog", "--config", resolved_config(config), "changelog", "--at", tag]
    return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(f"{name}<<{_OUTPUT_DELIMITER}\n{value}\n{_OUTPUT_DELIMITER}\n")


def push_tags(tags: list[str], token: str) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if token and repo:
        subprocess.run(
            [
                "git",
                "remote",
                "set-url",
                "origin",
                f"https://x-access-token:{token}@github.com/{repo}",
            ],
            check=True,
        )
    for tag in tags:
        subprocess.run(["git", "push", "origin", f"refs/tags/{tag}"], check=True)


def main() -> int:
    bump = os.environ.get("BUMP", "auto")
    config = os.environ.get("CONFIG", "")
    push = os.environ.get("PUSH", "true") == "true"
    token = os.environ.get("GH_TOKEN", "")

    if not run_check(config):
        print(
            "cog-bump: fix the commit message(s) above with a correctly-formatted "
            "follow-up commit and push again; nothing was released",
            file=sys.stderr,
        )
        return 1

    before = git_tags()
    run_cog(config, effective_bump_arg(bump, config, first_release=not before))
    new_tags = sorted(git_tags() - before)

    if not new_tags:
        print("cog-bump: nothing to release")
        write_output("tag", "")
        write_output("tags", "")
        write_output("notes", "")
        return 0

    print(f"cog-bump: created {', '.join(new_tags)}")
    write_output("tag", new_tags[0])
    write_output("tags", "\n".join(new_tags))
    # cocogitto's monorepo changelog isn't filtered by package, so a monorepo
    # builds its own notes (e.g. git-cliff --include-path).
    notes = "" if is_monorepo(config) else changelog(config, new_tags[0])
    write_output("notes", notes)

    if push:
        push_tags(new_tags, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
