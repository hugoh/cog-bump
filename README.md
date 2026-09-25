# cog-bump

Bumps a repo's version with [cocogitto](https://github.com/cocogitto/cocogitto)
using the bundled fleet `cog.toml` (`tag_prefix = "v"`, `disable_changelog`,
`disable_bump_commit` → tag-only: no commit, no `CHANGELOG.md`), then pushes the
new tag(s) by default. The `tag` / `tags` outputs are what cocogitto created, or
empty when nothing was releasable.

Expects the repo already checked out with full history (`fetch-depth: 0`).

Before bumping, `cog check <latest-tag>..HEAD` validates every commit since the
latest tag (any tag, including monorepo package tags, which `--from-latest-tag`
ignores) against Conventional Commits. `cog bump` otherwise just silently drops
a commit it can't parse from the version calculation — which can under-bump a
release (e.g. a mistyped `BREAKING CHANGE:` footer shipping as a patch) — so an
invalid commit message fails the action instead: no tag, no push. Recover by
pushing a correctly-formatted follow-up commit (an empty `fix!:`/`feat:` commit
works, since `disable_changelog` means there's no changelog entry to look at),
or by computing/pushing the tag yourself and having the calling workflow create
the release from that tag directly, bypassing this action. In a repo with no tag
yet, `cog check` validates the whole history instead, so a new repo can cut its
first release.

A repo's first release (no tags yet) is always `v0.1.0` with `bump: auto`,
whatever the commit types: from 0.0.0, cocogitto would otherwise release
`fix:`-only history as 0.0.1 and `chore:`-only history not at all. An explicit
`bump` still wins (`major` gives 1.0.0), and a monorepo `config:` keeps
`--auto`, since it tags each package on its own.

## Inputs

<!-- AUTO-DOC-INPUT:START - Do not remove or modify this section -->

| INPUT  | REQUIRED |         DEFAULT         |                                                         DESCRIPTION                                                          |
|--------|----------|-------------------------|------------------------------------------------------------------------------------------------------------------------------|
|  bump  |  false   |        `"auto"`         |                                              one of: auto, patch, minor, major                                               |
| config |  false   |                         | Path to a cog.toml to use instead of the bundled fleet config. Set this for monorepos that need a [monorepo.packages] table. |
|  push  |  false   |        `"true"`         |                                  Push the created tag(s) to origin (needs contents: write)                                   |
| token  |  false   | `"${{ github.token }}"` |                                                 Token used for the tag push                                                  |

<!-- AUTO-DOC-INPUT:END -->

## Outputs

<!-- AUTO-DOC-OUTPUT:START - Do not remove or modify this section -->

| OUTPUT |                                                                                    DESCRIPTION                                                                                    |
|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| notes  | `cog changelog --at <tag>` output for the first created tag, grouped by conventional commit type (`-t package_default` for a monorepo config). Empty when nothing was releasable. |
|  tag   |                                                         First tag cocogitto created, or empty when nothing was releasable                                                         |
|  tags  |                             All tags cocogitto created (newline-separated), empty when none. A monorepo `cog bump --auto` can create several at once.                             |

<!-- AUTO-DOC-OUTPUT:END -->

## Usage

```yaml
jobs:
  tag:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@<pinned-sha>
        with:
          persist-credentials: false
          fetch-depth: 0
      - id: bump
        uses: hugoh/cog-bump@<pinned-sha>
      - if: steps.bump.outputs.tag != ''
        run: echo "released ${{ steps.bump.outputs.tag }}"
```

## Monorepo

Pass `config:` pointing at a repo `cog.toml` with a `[monorepo.packages]` table
(cocogitto 7 schema — what `cocogitto-action@v4.2.0` installs; 6.x called it
`[packages]`, which is still recognized). `cog bump --auto` then tags every
package whose files changed since its last tag, and `tags` carries them all.
Keep `disable_bump_commit` so the release stays tag-only, and use
`monorepo_version_separator = "-v"` (**not** `tag_prefix`, which would stack
into `pkg-vv1.2.3`) for `pkg-v1.2.3` tags.

```yaml
      - id: bump
        uses: hugoh/cog-bump@<pinned-sha>
        with:
          config: cog.toml
      - if: steps.bump.outputs.tags != ''
        run: |
          while IFS= read -r t; do
            [ -n "$t" ] && echo "released $t"
          done <<< '${{ steps.bump.outputs.tags }}'
```

Used by the reusable
[`release.yml`](https://github.com/hugoh/gh-workflows/blob/main/.github/workflows/release.yml)
in `hugoh/gh-workflows` and by `spoon-tools`' `spoon-tag.yml`.

## History

Originally lived at `cog-bump/` inside
[`hugoh/gh-workflows`](https://github.com/hugoh/gh-workflows), alongside that
repo's other composite actions. Split out into its own repo since GitHub
Marketplace only publishes an Action whose `action.yml` sits at a repository
root.
