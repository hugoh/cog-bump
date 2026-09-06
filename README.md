# cog-bump

Bumps a repo's version with [cocogitto](https://github.com/cocogitto/cocogitto)
using the canonical fleet `cog.toml` (`tag_prefix = "v"`, `disable_changelog`,
`disable_bump_commit` → tag-only: no commit, no `CHANGELOG.md`), then pushes the
new tag by default. The `tag` output is the tag cocogitto created, or empty when
nothing was releasable.

Expects the repo already checked out with full history (`fetch-depth: 0`).

## Inputs

| Input | Required | Default | Purpose |
|---|---|---|---|
| `bump` | no | `auto` | `auto` \| `patch` \| `minor` \| `major` |
| `push` | no | `true` | Push the created tag to `origin` (needs `contents: write`) |
| `token` | no | `${{ github.token }}` | Token used for the tag push |

## Outputs

| Output | Value |
|---|---|
| `tag` | The tag cocogitto created, or empty when nothing was releasable |

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

Used by the reusable
[`release.yml`](https://github.com/hugoh/gh-workflows/blob/main/.github/workflows/release.yml)
in `hugoh/gh-workflows` and by `spoon-tools`' `spoon-tag.yml`.

## History

Originally lived at `cog-bump/` inside
[`hugoh/gh-workflows`](https://github.com/hugoh/gh-workflows), alongside that
repo's other composite actions. Split out into its own repo since GitHub
Marketplace only publishes an Action whose `action.yml` sits at a repository
root.
