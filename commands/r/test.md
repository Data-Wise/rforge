---
name: rforge:r:test
description: Run package tests (testthat) and report pass/fail/skip counts
argument-hint: "[package] [--changed] [--base <ref>] [--fail-on introduced|none]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: changed
    description: Run tests on the package(s) changed on this branch (vs --base) and tag each failing-test finding [introduced] vs [pre-existing] via a two-run merge-base baseline.
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; diff + baseline run vs merge-base(HEAD, base). Default dev.
    required: false
    type: string
    default: dev
  - name: fail-on
    description: "--changed exit policy: introduced (default) exits non-zero iff >=1 introduced finding; none is advisory."
    required: false
    type: string
    default: introduced
---

# R Package Tests

Run the suite via `testthat::test_local()` (self-loads the package via pkgload).

## Process
```bash
python3 -m lib.rcmd --kind test --path "<path>"
```

If `--changed`: `python3 -m lib.rcmd --kind test --changed --base "<ref>"
[--fail-on introduced|none]` — runs tests on the package(s) changed on this branch
and tags each failing-test finding `[introduced]` (new on your branch) vs
`[pre-existing]` (already failing at `merge-base(HEAD, base)`) via a second baseline
run in a detached worktree. `--fail-on introduced` (default) exits non-zero iff ≥1
introduced failure. Degrades to scope-only (no tagging) when no merge-base /
baseline worktree is available. Costs one extra test run (the baseline).

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
