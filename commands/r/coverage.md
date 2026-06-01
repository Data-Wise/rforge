---
name: rforge:r:coverage
description: Test coverage (covr) — total, per-file, and untested lines
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Coverage

Compute coverage via `covr::package_coverage()` (+ `zero_coverage()` for gaps).
`covr` is optional — if `engine_missing` includes `covr`, report 🟡 + install hint.

## Process
```bash
python3 -m lib.rcmd --kind coverage --path "<path>"
```

## Output Format
```markdown
## Coverage: {package} v{version}
### Total: {coverage.total_pct}%
### Lowest-covered files
{Top 5 ascending from coverage.per_file: "- R/foo.R — 12.0%"}
### Untested lines
{From coverage.untested: "- R/foo.R:12-18"}
### Recommended Actions
{Point at untested ranges ("add tests for R/foo.R:12-18"), or "Healthy ✅"}
```

## Related Commands
- `/rforge:r:test` — run the tests behind the coverage
