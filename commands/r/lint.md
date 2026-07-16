---
name: rforge:r:lint
description: Static analysis of the package (lintr) — grouped report
argument-hint: "[package] [--tidy] [--set-lintr] [--changed] [--base <ref>] [--fail-on introduced|none] [--no-cache]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: tidy
    description: Also run the tidyverse linter preset alongside the default one; report shows the additional tidy-only findings grouped by file.
    required: false
    type: boolean
    default: false
  - name: set-lintr
    description: "--tidy: write a .lintr activating the tidyverse preset permanently. Refuses to overwrite an existing .lintr."
    required: false
    type: boolean
    default: false
  - name: changed
    description: Lint the package(s) changed on this branch (vs --base) and tag each lint [introduced] vs [pre-existing] via a two-run merge-base baseline.
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; diff + baseline run vs merge-base(HEAD, base). Default dev.
    required: false
    type: string
    default: dev
  - name: fail-on
    description: "--changed exit policy: introduced (default) exits non-zero iff >=1 introduced lint; none is advisory."
    required: false
    type: string
    default: introduced
  - name: no-cache
    description: "--changed: bypass the baseline cache — force a fresh merge-base baseline run and skip writing it."
    required: false
    type: boolean
    default: false
---

# R Package Lint

Run `lintr::lint_package()` (read-only).
`lintr` is optional — if `engine_missing` includes `lintr`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind lint --path "<path>"

# Also run the tidyverse linter preset (issue #65)
python3 -m lib.rcmd --kind lint --path "<path>" --tidy

# ...and write a .lintr activating it permanently
python3 -m lib.rcmd --kind lint --path "<path>" --tidy --set-lintr
```

### `--tidy`

`tidyverse_linters()` was removed in lintr 3.x — the preset is built explicitly
(`object_name_linter("snake_case")`, `brace_linter`, `spaces_inside_linter`,
`trailing_whitespace_linter`, `semicolon_linter`) and run **alongside** the
default preset, not instead of it. The envelope's `lint.tidy` block reports
only the *additional* findings the tidy preset surfaces (same file+line+linter
already in the default run are not double-counted), grouped by file —
`object_name_linter` in particular can produce hundreds of hits on a package
with legacy `dot.case` public API arguments (e.g. `mu.x`, `se.y`); these
can't be renamed without a breaking release, so call that out explicitly
rather than presenting raw hit counts.

`--set-lintr` writes `.lintr` to the package root so the preset applies on
every future lint run without `--tidy`. It refuses to overwrite an existing
`.lintr` — remove it manually first if you want to replace it.

If `--changed`: `python3 -m lib.rcmd --kind lint --changed --base "<ref>"
[--fail-on introduced|none] [--no-cache]` — lints the package(s) changed on this branch and tags
each lint `[introduced]` (new on your branch) vs `[pre-existing]` (already present at
`merge-base(HEAD, base)`) via a second baseline run in a detached worktree. An
`[introduced]` lint whose file still has **uncommitted** changes is further refined to
`[uncommitted]` (you caused it with edits you haven't committed yet) — a file-level
refinement (no third run), so all introduced lints in a dirty file tag `[uncommitted]`.
`[uncommitted]` counts as introduced for `--fail-on`. `--fail-on introduced` (default)
exits non-zero iff ≥1 introduced lint (incl. `[uncommitted]`). Degrades to
scope-only (no tagging) when no merge-base / baseline worktree is available. Costs
one extra lint run (the baseline) — but that baseline is **cached per package**
under `~/.rforge/baseline-cache/` (keyed by repo + merge-base SHA + kind +
package + flags) and self-invalidates when `--base` advances, so a repeat
`--changed` run reuses each already-baselined package and re-runs only the uncached
ones. Pass `--no-cache` to force a fresh baseline; clear it with
`python3 -m lib.changed --clear-cache`.

## Output Format
```markdown
## Lint: {package} v{version}
### Status: {🟢 0 lints / 🟡 {lint.count} lints}
{Group lint.lints by file: "R/foo.R:3 — object_name_linter: <message>"}
{If --tidy: ### Tidyverse-only findings: {lint.tidy.count} additional
{Group lint.tidy.lints by file via lint.tidy.by_file: "R/foo.R (12)"}}
### Recommended Actions
{Top offenders to fix, or "Clean ✅"}
```

## Related Commands
- `/rforge:r:style` — auto-format (fixes many style lints)
- `/rforge:r:tidy` — full tidyverse-conventions audit (this preset + DESCRIPTION normalization + roxygen completeness + NEWS.md header)
