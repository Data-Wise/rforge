---
name: rforge-check
description: Run Rforge R package checks and explain errors, warnings, and NOTEs. Use for R CMD check or CRAN-style package validation.
---

# R package checks

Run the existing Rforge check engine; do not reproduce its R logic.

1. Resolve the target package to an absolute path from the user's workspace,
   before changing the execution directory. Read its project instructions and
   check any simulation, build, or submission holds.
2. Locate the local Rforge source checkout (personal default:
   `/Users/davood/projects/dev-tools/rforge`). Verify `lib/rcmd.py` exists.
   This skill package contains instructions, not the engine. If unavailable,
   report the missing checkout rather than substituting a Claude command or MCP.
3. Use Python 3.10+ with the checkout as the tool's working directory:

   ```text
   python3 -m lib.rcmd --kind check --path /absolute/package/path
   ```

   Quote paths safely when passing them to a shell. Use `--as-cran`, `--strict`,
   or `--incoming` only when requested. Read `commands/r/check.md` in that checkout
   for requested advanced flags such as `--changed`; choose the package's actual
   comparison branch rather than assuming it has `dev`.
4. Read the JSON envelope and retain the check log path. Explain errors,
   warnings, and real versus classified spurious NOTEs. An unavailable R engine,
   missing dependency, skipped stage, or malformed output is not a passing check.
   Preserve introduced/pre-existing tags only when the engine actually computed
   the baseline; report fallback scope explicitly.
5. State the package, options, result, and most useful next fix. Package checks
   execute package R code and can create build/check artifacts. Do not install
   dependencies, edit source, or rerun expensive checks merely to hide a failure.
   Fixes follow the user's requested scope and the package's rules.

This workflow does not submit to CRAN, release, deploy, or change hook trust.
