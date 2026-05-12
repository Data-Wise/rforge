---
name: rforge:r:check
description: Run R CMD check on package with smart output parsing
---

# R Package Quick Check

You are performing a quick health check on an R package.

## Task

Check R package at: **$ARGUMENTS**

If no path specified, check current directory.

## Quick Check Process

### Step 1: Basic Info
Read DESCRIPTION file:
- Package name and version
- Dependencies (Imports, Suggests)
- R version requirement

### Step 2: R CMD Check
Run `R CMD check` via the Bash tool (e.g., `R CMD check --as-cran <path>`).

### Step 3: Test Summary
Run the package's tests via Bash (e.g., `Rscript -e 'devtools::test()'`).
`R CMD check` also runs them and surfaces failures.

### Step 4: Documentation Check
- Are all exported functions documented?
- Do examples run without error?
- Is there a README?

### Step 5: Code Quality
- Any obvious style issues?
- Are there TODOs or FIXMEs?
- Is test coverage adequate?

## Output Format

```markdown
## Package Check: [package-name] v[version]

### Status: 🟢 / 🟡 / 🔴

### R CMD Check
- Errors: X
- Warnings: Y
- Notes: Z

### Tests
- Passed: X
- Failed: Y
- Coverage: Z%

### Documentation
- [ ] All exports documented
- [ ] Examples run
- [ ] README exists

### Issues Found
1. [Issue 1]
2. [Issue 2]

### Recommended Actions
1. [Action 1]
2. [Action 2]
```

## Tools to Use
- Bash (to run `R CMD check`, `Rscript`, `devtools::test()`)
- Read (for DESCRIPTION, README)
- Grep (for TODOs, FIXMEs)

## Related Commands

- `/rforge:thorough` - Comprehensive multi-package check including R CMD check
- `/rforge:status` - Lightweight health snapshot without R subprocess
- `/rforge:docs:check` - Documentation drift check (complements R CMD check)
