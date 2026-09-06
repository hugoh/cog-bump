#!/usr/bin/env python3
"""Bump versions with cocogitto (tag-only), then emit and push the new tags.

Driven entirely by environment variables so the composite action can call it
without argument plumbing:

    BUMP        auto | patch | minor | major        (default: auto)
    CONFIG      path to a cog.toml to use            (default: bundled cog.toml)
    PUSH        "true" to push the new tags          (default: "true")
    GH_TOKEN    token for the tag push               (default: unset)

cocogitto is run with ``--config`` so a monorepo repo can supply its own
``[packages]`` table; ``cog bump --auto`` then tags every package whose files
changed. Any tags that appear are reported (``tag`` = first, ``tags`` = all,
newline-separated) via ``$GITHUB_OUTPUT`` and pushed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_OUTPUT_DELIMITER = "COG_BUMP_EOF"


def git_tags() -> set[str]:
    out = subprocess.run(
        ["git", "tag"], check=True, text=True, capture_output=True
    ).stdout
    return {line for line in out.splitlines() if line}


def bump_arg(bump: str) -> str:
    return "--auto" if bump == "auto" else f"--{bump}"


def bundled_config() -> str:
    return str(Path(__file__).with_name("cog.toml"))


def run_cog(config: str, arg: str) -> None:
    cmd = ["cog", "--config", config or bundled_config(), "bump", arg]
    # cocogitto exits non-zero when there is nothing to release; the tag diff,
    # not the exit code, tells us what actually happened.
    subprocess.run(cmd, check=False)


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

    before = git_tags()
    run_cog(config, bump_arg(bump))
    new_tags = sorted(git_tags() - before)

    if not new_tags:
        print("cog-bump: nothing to release")
        write_output("tag", "")
        write_output("tags", "")
        return 0

    print(f"cog-bump: created {', '.join(new_tags)}")
    write_output("tag", new_tags[0])
    write_output("tags", "\n".join(new_tags))

    if push:
        push_tags(new_tags, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
