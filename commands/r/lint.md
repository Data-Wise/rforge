---
name: rforge:r:lint
description: Static analysis of the package (lintr) — grouped report
argument-hint: "[package] [--changed] [--base <ref>] [--fail-on introduced|none] [--no-cache]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
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
```

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
one extra lint run (the baseline) — but that baseline is **cached**
under `~/.rforge/baseline-cache/` (keyed by repo + merge-base SHA + kind +
changed-package set + flags) and self-invalidates when `--base` advances, so a
repeat `--changed` run reuses it. Pass `--no-cache` to force a fresh baseline; clear
it with `python3 -m lib.changed --clear-cache`.

## Output Format
```markdown
## Lint: {package} v{version}
### Status: {🟢 0 lints / 🟡 {lint.count} lints}
{Group lint.lints by file: "R/foo.R:3 — object_name_linter: <message>"}
### Recommended Actions
{Top offenders to fix, or "Clean ✅"}
```

## Related Commands
- `/rforge:r:style` — auto-format (fixes many style lints)
