---
name: rforge:r:goodpractice
description: Advisory best-practice bundle — goodpractice checks (opt-in, not part of r:cycle)
argument-hint: "[package]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Advisory Best-Practice Check

Run `goodpractice::gp()` — an **advisory opt-in** bundle that re-runs R CMD
check, lint (lintr), and coverage (covr) under the hood, plus additional
best-practice checks (cyclomatic complexity, TODO/FIXME scan, DESCRIPTION
completeness, etc.).

**Not part of `/rforge:r:cycle`** — `cycle` already runs check, test, and
document. Adding goodpractice there would double-run R CMD check, lint, and
coverage. Use `/rforge:r:goodpractice` after the dev cycle as a pre-submission
advisory pass, not on every save.

`goodpractice` is optional — if `engine_missing` includes it, report 🟡 + hint:

```
install.packages("goodpractice")
```

## Process

```bash
python3 -m lib.rcmd --kind goodpractice --path "<path>"
```

## Output Format

````markdown
## Best-Practice Checks: {package} v{version}
### Status: {🟢 all checks passed / 🟡 advisories}
- Advisories: {goodpractice.count}
{If count > 0: list each entry from goodpractice.checks}
### Recommended Actions
{Address advisories before submission; or "clean ✅"}
````

## Related Commands

- `/rforge:r:check` — R CMD check (goodpractice re-runs this internally; run both deliberately)
- `/rforge:r:lint` — lintr lint pass (goodpractice re-runs lintr; use separately for faster feedback)
- `/rforge:r:coverage` — covr coverage (goodpractice re-runs covr; use separately to avoid double-work in the dev loop)
- `/rforge:r:cran-prep` — full CRAN submission gate (includes goodpractice as one step)
