---
name: rforge:r:lint
description: Static analysis of the package (lintr) — grouped report
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Lint

Run `lintr::lint_package()` (read-only).
`lintr` is optional — if `engine_missing` includes `lintr`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind lint --path "<path>"
```

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
