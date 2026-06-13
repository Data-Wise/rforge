---
name: rforge:r:lint
description: Static analysis of the package (lintr) — grouped report
argument-hint: "[package] [--changed] [--base <ref>] [--fail-on introduced|none]"
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
---

# R Package Lint

Run `lintr::lint_package()` (read-only).
`lintr` is optional — if `engine_missing` includes `lintr`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind lint --path "<path>"
```

If `--changed`: `python3 -m lib.rcmd --kind lint --changed --base "<ref>"
[--fail-on introduced|none]` — lints the package(s) changed on this branch and tags
each lint `[introduced]` (new on your branch) vs `[pre-existing]` (already present at
`merge-base(HEAD, base)`) via a second baseline run in a detached worktree.
`--fail-on introduced` (default) exits non-zero iff ≥1 introduced lint. Degrades to
scope-only (no tagging) when no merge-base / baseline worktree is available. Costs
one extra lint run (the baseline).

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
