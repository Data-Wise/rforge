---
name: rforge-check
description: Run Rforge R package checks and explain errors, warnings, and NOTEs. Use for R CMD check or CRAN-style package validation.
---

# R package checks

Reuse Rforge's engine; do not reproduce its R logic.

1. Resolve the requested package to an existing absolute path before changing
   execution directories. Read its project instructions and build/job holds.
   Require a DESCRIPTION at the chosen package root; never substitute a sibling.
2. Locate the user's Rforge checkout (personal default:
   `/Users/davood/projects/dev-tools/rforge`) or an explicitly supplied checkout.
   Verify `lib/rcmd.py` supports check `output_format`, `incomplete`, and
   `check.log_paths`/`check.exit_status`. An older checkout must be updated or
   explicitly replaced
   with the pilot checkout before running; do not certify results from it.
   Missing engine or Python 3.10+ means unavailable, not a passing check.
3. From that checkout, use a supported Python interpreter and quoted paths:

   ```text
   python3 -m lib.rcmd --kind check --path /absolute/package/path --as-cran
   ```

   Default: one `--as-cran` pass, matching Rforge. Omit `--as-cran` only for an
   explicit plain R CMD check request. For requested `--strict`, replace the
   ordinary pass with two labeled calls, each retaining `--as-cran`:
   `--flavor depends` (noSuggests), then `--flavor suggests` (suggests-only).
   Each flavor executes donttest examples. Raw `--strict` alone does not run
   both flavors. Requested `--incoming` implies those strict calls plus one
   labeled `--incoming` call; that engine call internally runs two incoming
   flavors. Report each result and log separately; this is multiple check runs.
   Advanced `--changed` baseline tagging is outside this small pilot: explain
   that limitation rather than passing it through or calling a no-op a check.
4. Read each JSON envelope. Require `output_format: json`, `incomplete: false`,
   no missing engine, real check arrays, and zero for every `check.exit_status`
   before describing a completed
   check. Nonzero exit, malformed output, unavailable dependencies, or skipped
   work cannot pass. Explain errors, warnings, and classified NOTEs.
   Report each `check.log_paths` entry only after verifying the file exists.
   If empty, say the R check log is unavailable; never invent a path or
   substitute the adapter JSON for an R log. Any failed pass fails the workflow.
5. Report package, engine checkout, exact options, per-pass results/logs, and
   the most useful next fix. Checks execute package R code and leave temporary
   build/check directories; report them without removing evidence automatically.
   Do not install dependencies, edit source, or repeat expensive checks unless
   the user's task calls for it. Respect package holds.

This workflow does not submit, release, deploy, or change hook trust.
