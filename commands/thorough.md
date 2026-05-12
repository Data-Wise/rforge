---
name: rforge:thorough
description: Comprehensive R package analysis (status rollup plus user-run R checks)
argument-hint: Optional context (e.g., "Prepare for CRAN release")
arguments:
  - name: context
    description: What to focus the thorough analysis on (e.g., "CRAN prep")
    required: false
    type: string
  - name: package
    description: Optional package path (defaults to current directory)
    required: false
    type: string
---

# /rforge:thorough - Comprehensive R Package Analysis

Comprehensive analysis built on top of the in-plugin status module, plus R-side checks that the
user runs in their own shell.

## Usage

```bash
# Thorough rundown
/rforge:thorough

# With context (free-form, used for narration only)
/rforge:thorough "Prepare RMediation for CRAN"
```

## What It Does

1. **Run the lib status rollup** for the full ecosystem picture:

   ```bash
   python3 -m lib.status --path . --format text
   ```

   Use `--format json` if you want to post-process.

2. **Recommend the user run heavier R checks themselves** (these are not invoked by this command —
   they require an R toolchain and can take minutes):

   ```bash
   # Inside the package directory
   R CMD check --as-cran .
   Rscript -e 'devtools::test()'
   Rscript -e 'covr::package_coverage()'
   ```

3. **Combine the lib status output with whatever R-side results the user shares** for a release
   readiness summary.

## When to Use

- ✅ Preparing for CRAN submission
- ✅ Release readiness review
- ✅ Want broader picture than `/rforge:quick`

**Don't use** when you just need a fast snapshot — use `/rforge:quick` instead.

## ADHD Considerations

- ⏰ R-side checks can take minutes; run them in a separate terminal and return to this command
- 📊 The lib status portion completes in seconds — start there
- 💾 Save R CMD check output to a file if you want to paste it back

## Related Commands

- `/rforge:quick` - Ultra-fast snapshot (seconds)
- `/rforge:analyze` - Balanced analysis with recommendations
- `/rforge:status` - Status rollup only

## Notes

Mode-aware depth (`full_check`, `coverage`, `performance`) and background R task orchestration
from the previous MCP-backed version were descoped in v1.3.0 as part of the scope correction.
Heavy R checks now run in the user's own shell; this command focuses on aggregating the
lib-module output and pointing at the right R-side tools.
