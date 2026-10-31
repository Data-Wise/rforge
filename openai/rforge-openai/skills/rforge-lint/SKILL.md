---
name: rforge-lint
description: Run Rforge package lint and diagnose differences from CI, including missing names in test helpers and stale installed packages.
---

# R package lint

Reuse Rforge's existing `lib.rcmd` engine; do not reproduce its R logic.

1. Resolve the requested package to an existing absolute path with DESCRIPTION.
   Read its instructions, holds, `.lintr`, startup files and lint CI workflow.
   Preserve the configured linters and exclusions. Never disable a diagnostic
   just to obtain a clean result.
2. Locate the user's Rforge checkout (personal default:
   `/Users/davood/projects/dev-tools/rforge`) or an explicitly supplied checkout.
   Verify `lib.rcmd` supports `--kind lint`. Missing engine, Python 3.10+, R,
   `jsonlite`, or `lintr` means unavailable, never passing.
3. Establish the R environment before claiming CI parity. Record R/lintr
   versions, `.libPaths()`, the installed target package path/version, startup
   behavior and the source ref being linted. Use a fresh R process without
   `devtools::load_all()`, `pkgload::load_all()`, or attaching testthat first.
   A workflow that installs the current package needs that same source installed
   in the selected library. Matching version strings alone do not prove this:
   use an install receipt tied to the source ref or report provenance unknown.
   An older installed namespace can create unrelated missing-name diagnostics.
   If setup differs or provenance is unknown, report local findings and mark
   CI parity unverified. Do not install/reinstall packages without authorization.
   Honor an explicitly selected library through `R_LIBS`/`R_LIBS_USER` inherited
   by the engine; verify the effective library from R, not just the variable.
4. From the engine checkout, use supported Python and quoted absolute paths:

   ```text
   python3 -m lib.rcmd --kind lint --path "/absolute/package/path"
   ```

   This starts a separate Rscript process but honors R startup configuration;
   ensure it does not preload the development package or testthat. Match CI's
   startup/environment settings rather than silently changing them. A loaded
   interactive lint is supplementary evidence only. For missing assertions in
   helpers outside `test_that()`, prefer `testthat::expect_true(...)` and the
   corresponding explicit namespace for other assertion helpers. Do not attach
   testthat globally or add blanket suppressions to mask the finding.
5. Read the JSON envelope, not only the process exit status. Require no
   `engine_missing`, no error/timeout/fallback messages, and a real `lint` block
   with consistent `count` and `lints` before reporting a completed scan.
   Zero means clean only for that configuration and environment. Lints may be
   advisory with exit zero; missing dependencies can also return warning status
   with count zero. Neither is a passing CI gate. Group findings by file/line
   and linter; rerun after an authorized repair in the same fresh environment.
6. Report package/source ref, engine ref, exact options, environment evidence,
   finding count and whether CI parity was established. Advanced `--changed`
   baseline tagging and `--tidy` presets are outside this focused workflow;
   explain that limitation rather than claiming those checks ran. Do not run
   formatting, write `.lintr`, push, submit, or dispatch hosted CI implicitly.
