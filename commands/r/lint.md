---
name: rforge:r:lint
description: Static analysis of the package (lintr) — grouped report
argument-hint: "[package] [--changed] [--base <ref>]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: changed
    description: Scope lint to packages changed on this branch (no finding tagging — lints are reported as-is)
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; diff vs merge-base(HEAD, base). Default HEAD
    required: false
    type: string
    default: HEAD
---

# R Package Lint

Run `lintr::lint_package()` (read-only).
`lintr` is optional — if `engine_missing` includes `lintr`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind lint --path "<path>"
```

If `--changed`: `python3 -m lib.rcmd --kind lint --changed --base "<ref>"` — lints
only the package(s) changed on this branch (scope-only, no tagging).

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
