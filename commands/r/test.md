---
name: rforge:r:test
description: Run package tests (testthat) and report pass/fail/skip counts
argument-hint: "[package] [--changed] [--base <ref>]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: changed
    description: Scope tests to packages changed on this branch (no finding tagging — test results are reported as-is)
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; diff vs merge-base(HEAD, base). Default HEAD
    required: false
    type: string
    default: HEAD
---

# R Package Tests

Run the suite via `testthat::test_local()` (self-loads the package via pkgload).

## Process
```bash
python3 -m lib.rcmd --kind test --path "<path>"
```

If `--changed`: `python3 -m lib.rcmd --kind test --changed --base "<ref>"` — runs
tests only for the package(s) changed on this branch (scope-only, no tagging).

## Output Format
```markdown
## Tests: {package} v{version}
### Status: {🟢 0 failed / 🟡 skips or warnings / 🔴 failures}
- Passed: {tests.passed}
- Failed: {tests.failed}
- Skipped: {tests.skipped}
- Warnings: {tests.warnings}
{If failing_files: list under "### Failing files"}
### Recommended Actions
{Next steps or "All green ✅"}
```

## Related Commands
- `/rforge:r:cycle` — document → test → check
- `/rforge:r:coverage` — which lines the tests miss
