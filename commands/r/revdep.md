---
name: rforge:r:revdep
description: Reverse-dependency check against CRAN downstream packages (revdepcheck)
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Reverse-Dependency Check

Run `revdepcheck::revdep_check()` — a hard CRAN obligation for API-changing
updates. **External CRAN downstream deps**, distinct from rforge's internal
`/rforge:deps`/`/rforge:impact` (ecosystem edges).

`revdepcheck` is optional — if `engine_missing` includes it, report 🟡 + hint.
Note: this can be slow (it builds downstream packages).

## Process
```bash
python3 -m lib.rcmd --kind revdep --path "<path>"
```

## Output Format
```markdown
## Reverse Dependencies: {package} v{version}
### Status: {🟢 none broken / 🟡 new problems / 🔴 broken downstream}
- Broken: {revdep.broken}
- New problems: {revdep.new_problems}
{If broken/problems: list each; point at revdep/problems.md}
### Recommended Actions
{Contact affected maintainers ≥2 weeks ahead; note in submission. Or "clean ✅"}
```

## Related Commands
- `/rforge:r:cran-prep` — runs revdep as part of the submission gate
- `/rforge:deps` / `/rforge:impact` — **internal** ecosystem deps (not CRAN downstream)
