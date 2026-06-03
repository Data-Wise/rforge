# 📖 RForge Commands Reference

!!! tip "TL;DR (30 seconds)"
    - **What:** Full per-command reference (parameters, examples, output format).
    - **Why:** REFCARD is a cheat sheet; this page is the deep dive.
    - **How:** Jump to a category below, or `Ctrl+F` for a specific command.
    - **Next:** [REFCARD](REFCARD.md) for the at-a-glance summary.

Complete reference for all **33** RForge commands. Commands are organized by category with usage examples and parameter details.

## Command Categories

- [Setup & State](#setup-state) (1 command)
- [Status & Analysis](#status-analysis) (4 commands)
- [Ecosystem Management](#ecosystem-management) (5 commands)
- [Documentation & Tasks](#documentation-tasks) (4 commands)
- [Health Checks](#health-checks) (2 commands)
- [R Development Cycle](#r-development-cycle) (9 commands)
- [R Quality](#r-quality) (5 commands)
- [CRAN Submission](#cran-submission) (5 commands)

---

## Setup & State

### /rforge:init

Initialize the active rforge context for the current R package or ecosystem. Writes per-user state to `~/.rforge/context.json` so other commands know which package you're working on.

**Usage:**
```bash
/rforge:init [--path PATH] [--quick] [--format FORMAT]
```

**Parameters:**
- `--path` (optional) — Package or ecosystem root (defaults to current directory)
- `--quick` (optional) — Skip comprehensive analysis (faster, lighter context file)
- `--format` (optional) — Output format: `text` (default) or `json`

**Examples:**
```bash
# Initialize from the current directory
/rforge:init

# Quick init (skip analysis)
/rforge:init --quick

# Initialize a specific package
/rforge:init --path ~/projects/medfit
```

**What this does:**
- Detects the package or ecosystem layout (uses `lib/discovery.py`)
- Writes `~/.rforge/context.json` marking the path as the active context
- Idempotent — re-running on the same path is a no-op for state, may refresh analysis
- Per-user, not per-package — switching contexts overwrites the state file

**When to run:** First time using rforge on a package, or when switching active context. Other commands (`/rforge:status`, `/rforge:deps`, etc.) read this file to know which package they're operating on.

**Time budget:** <5s (`--quick`), <15s (default)

**Underlying module:** `python3 -m lib.init` — see [init API reference](reference/init.md).

---

## Status & Analysis

### /rforge:status

Quick ecosystem-wide status dashboard with mode-specific detail levels.

**Usage:**
```bash
/rforge:status [package] [--mode MODE] [--format FORMAT]
```

**Parameters:**
- `package` (optional) - Package name (defaults to current or ecosystem)
- `--mode` (optional) - Status detail level: `default`, `debug`, `optimize`, `release`
- `--format` (optional) - Output format: `terminal`, `json`, `markdown`

**Examples:**
```bash
# Quick health check (default mode)
/rforge:status

# Debug mode for detailed diagnostics
/rforge:status --mode debug

# JSON output for automation
/rforge:status --format json

# Specific package status
/rforge:status mypackage --mode release
```

**Output includes:**
- Health score (0-100)
- Package version and path
- Git status
- Dependencies status
- Test results
- Coverage metrics

**Time budget:** <10s (default), up to 300s (release mode)

---

### /rforge:analyze

Deep analysis with mode system support and intelligent recommendations.

**Usage:**
```bash
/rforge:analyze [description] [--mode MODE] [--format FORMAT]
```

**Parameters:**
- `description` (optional) - What to analyze or focus on
- `--mode` (optional) - Analysis depth: `default`, `debug`, `optimize`, `release`
- `--format` (optional) - Output format: `terminal`, `json`, `markdown`

**Examples:**
```bash
# Balanced analysis
/rforge:analyze "Check package health"

# Debug mode for investigating issues
/rforge:analyze --mode debug "Why are tests failing?"

# Release mode for CRAN preparation
/rforge:analyze --mode release "Prepare for CRAN submission"

# Performance analysis
/rforge:analyze --mode optimize "Identify bottlenecks"
```

**Performs:**
- Pattern recognition (CODE_CHANGE, BUG_FIX, CRAN_RELEASE, etc.)
- Tool selection based on context
- Parallel pure-Python `lib/` module execution (no MCP server)
- Results synthesis with actionable recommendations

**Time budget:** <30s (default), up to 300s (release mode)

---

### /rforge:quick

Ultra-fast status check using only quick tools (<10 seconds).

**Usage:**
```bash
/rforge:quick [description]
```

**Parameters:**
- `description` (optional) - Brief context for the check

**Examples:**
```bash
# Morning stand-up check
/rforge:quick

# Pre-commit validation
/rforge:quick "Before committing changes"
```

**Provides:**
- Basic package info
- Git status
- Critical issues only
- No deep analysis

**Time budget:** <10s (guaranteed)

---

### /rforge:thorough

Comprehensive analysis with R CMD check integration (2-5 minutes).

**Usage:**
```bash
/rforge:thorough [description]
```

**Parameters:**
- `description` (optional) - Analysis context

**Examples:**
```bash
# Full CRAN preparation
/rforge:thorough "Prepare for CRAN submission"

# Deep quality audit
/rforge:thorough "Pre-release audit"
```

**Includes:**
- R CMD check execution
- Full dependency tree analysis
- Complete test suite with coverage
- Documentation completeness check
- All quality metrics

**Time budget:** 2-5 minutes

---

## Ecosystem Management

### /rforge:detect

Auto-detect project structure (single package, ecosystem, or hybrid).

**Usage:**
```bash
/rforge:detect
```

**No parameters**

**Examples:**
```bash
# Detect current directory structure
/rforge:detect
```

**Output:**
- Project type: single, ecosystem, or hybrid
- Package count and names
- Directory structure summary
- Dependency relationships

---

### /rforge:cascade

Plan coordinated updates across dependent packages.

**Usage:**
```bash
/rforge:cascade [description]
```

**Parameters:**
- `description` (optional) - What's changing and why

**Examples:**
```bash
# Plan update cascade
/rforge:cascade "Update base package dependency from v1 to v2"

# Version bump cascade
/rforge:cascade "Major version bump in core package"
```

**Analyzes:**
- Dependency graph
- Update order (respecting dependencies)
- Breaking changes impact
- Test coverage for affected packages

---

### /rforge:impact

Analyze change impact across ecosystem packages.

**Usage:**
```bash
/rforge:impact [description]
```

**Parameters:**
- `description` (optional) - What changed

**Examples:**
```bash
# API change impact
/rforge:impact "Changed function signature in base package"

# Dependency update impact
/rforge:impact "Updated ggplot2 to v3.5.0"
```

**Reports:**
- Affected packages
- Breaking vs non-breaking changes
- Required updates
- Test implications

---

### /rforge:release

Plan CRAN submission sequence based on dependencies.

**Usage:**
```bash
/rforge:release
```

**No parameters**

**Examples:**
```bash
# Generate release plan
/rforge:release
```

**Provides:**
- Submission order (base packages first)
- Pre-submission checklist per package
- Version compatibility check
- Timeline estimate

---

### /rforge:deps

Build and visualize dependency graph across R package ecosystem.

**Usage:**
```bash
/rforge:deps [--format FORMAT]
```

**Parameters:**
- `--format` (optional) - Output format: `terminal`, `json`, `mermaid`

**Examples:**
```bash
# Terminal visualization
/rforge:deps

# Mermaid diagram for documentation
/rforge:deps --format mermaid > deps.mmd

# JSON for programmatic use
/rforge:deps --format json
```

**Output:**
- Dependency graph (directed acyclic graph)
- Import vs Suggest relationships
- Circular dependency detection
- External dependencies

---

## Documentation & Tasks

### /rforge:docs:check

Check for documentation drift and inconsistencies across packages.

**Usage:**
```bash
/rforge:docs:check
```

**No parameters**

**Examples:**
```bash
# Check documentation status
/rforge:docs:check
```

**Validates:**
- Exported functions have documentation
- Examples are runnable
- NAMESPACE consistency with documentation
- Version numbers match across files

---

### /rforge:complete

Mark tasks complete with automatic documentation cascade.

**Usage:**
```bash
/rforge:complete [task_description]
```

**Parameters:**
- `task_description` (optional) - What was completed

**Examples:**
```bash
# Mark task complete
/rforge:complete "Implemented bootstrap CI method"

# Trigger doc cascade
/rforge:complete "Fixed critical bug in mediation function"
```

**Actions:**
- Updates task tracking
- Triggers documentation updates
- Updates CHANGELOG if configured
- Git commit prompt (optional)

---

### /rforge:capture

Quick capture ideas and tasks for later (with automatic doc cascade detection).

**Usage:**
```bash
/rforge:capture [idea]
```

**Parameters:**
- `idea` (required) - What to capture

**Examples:**
```bash
# Capture feature idea
/rforge:capture "Add support for weighted mediation"

# Capture bug note
/rforge:capture "Edge case: NA handling in bootstrap"
```

**Stores:**
- Idea with timestamp
- Context (current package, branch)
- Suggested next actions

---

### /rforge:next

Get ecosystem-aware next task recommendation.

**Usage:**
```bash
/rforge:next
```

**No parameters**

**Examples:**
```bash
# Get next task suggestion
/rforge:next
```

**Considers:**
- Unfinished tasks
- Blocking issues
- Dependency order
- Quick wins
- Priority indicators

**Output:**
- ONE recommended task
- WHY this task (reasoning)
- Time estimate
- 2-3 alternatives

---

## Health Checks

### /rforge:health

Comprehensive ecosystem health metrics with visual dashboard.

**Usage:**
```bash
/rforge:health [--format FORMAT]
```

**Parameters:**
- `--format` (optional) - Output format: `terminal`, `json`, `markdown`

**Examples:**
```bash
# Visual health dashboard
/rforge:health

# JSON metrics
/rforge:health --format json
```

**Metrics:**
- Overall health score (0-100)
- Per-package scores
- Test coverage distribution
- Dependency freshness
- Documentation completeness

---

### /rforge:r:check

R CMD check integration with detailed error reporting.

**Usage:**
```bash
/rforge:r:check [package]
```

**Parameters:**
- `package` (optional) - Package to check (defaults to current)

**Examples:**
```bash
# Check current package
/rforge:r:check

# Check specific package
/rforge:r:check mypackage
```

**Executes:**
- R CMD check with standard flags
- Parses output for errors/warnings/notes
- Categorizes issues
- Suggests fixes

**Note:** This can take 1-5 minutes depending on package size.

---

## R Development Cycle

### /rforge:r:load

Load the package into a namespace via `pkgload::load_all()` for interactive development.

**Usage:**

```bash
/rforge:r:load [package]
```

**Parameters:**

- `package` (optional) - Package path to load (defaults to current directory)

**Examples:**

```bash
# Load current package
/rforge:r:load

# Load specific package
/rforge:r:load ~/projects/mypackage
```

**Executes:**

- Simulate-installs the package into a namespace via `pkgload::load_all()`
- Reports load status and any errors

**Related commands:** `/rforge:r:test` (auto-loads inside test_local), `/rforge:r:document`

---

### /rforge:r:document

Regenerate `man/*.Rd` documentation and `NAMESPACE` via `roxygen2::roxygenize()`.

**Usage:**

```bash
/rforge:r:document [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Regenerate docs for current package
/rforge:r:document
```

**Executes:**

- Runs `roxygen2::roxygenize()` (the blessed regeneration path — hand-edits to `man/*.Rd` are blocked by the PreToolUse hook)
- Reports success and recommends reviewing `git diff man/ NAMESPACE`

**Related commands:** `/rforge:r:check` (verify after regenerating), `/rforge:docs:check` (detect drift)

---

### /rforge:r:test

Run package tests via `testthat` and report pass/fail/skip counts.

**Usage:**

```bash
/rforge:r:test [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Test current package
/rforge:r:test
```

**Executes:**

- Runs `testthat::test_local()` (self-loads the package via pkgload)
- Reports passed, failed, skipped, and warning counts
- Lists failing files when failures are present

**Related commands:** `/rforge:r:cycle` (document → test → check), `/rforge:r:coverage`

---

### /rforge:r:coverage

Compute test coverage via `covr` — total percentage, per-file breakdown, and untested lines.

**Usage:**

```bash
/rforge:r:coverage [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Coverage for current package
/rforge:r:coverage
```

**Executes:**

- Runs `covr::package_coverage()` plus `zero_coverage()` for gap detection
- Reports total %, lowest-covered files, and specific untested line ranges
- If `covr` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:test`

---

### /rforge:r:build

Build a source tarball via `pkgbuild::build()` and report the artifact path and size.

**Usage:**

```bash
/rforge:r:build [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Build current package
/rforge:r:build
```

**Executes:**

- Builds a `.tar.gz` source tarball via `pkgbuild::build()`
- Reports the artifact path and size in KB

**Related commands:** `/rforge:r:check` (validate before building), `/rforge:r:install`

---

### /rforge:r:install

Install the package locally via `R CMD INSTALL` and report the installed version.

**Usage:**

```bash
/rforge:r:install [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Install current package
/rforge:r:install
```

**Executes:**

- Runs `R CMD INSTALL` on the package
- Reports exit status and installed version, or surfaces dependency errors

**Related commands:** `/rforge:r:build`

---

### /rforge:r:site

Build the pkgdown website (vignettes → articles) with optional preview.

**Usage:**

```bash
/rforge:r:site [package] [--preview] [--strict] [--articles-only] [--devel]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)
- `--preview` (optional) - Open the built site via `pkgdown::preview_site()`
- `--strict` (optional) - Fail-fast config check via `check_pkgdown` (useful in CI)
- `--articles-only` (optional) - Build only articles/vignettes (reinstalls first)
- `--devel` (optional) - Fast in-process build via `load_all` (lower fidelity)

**Examples:**

```bash
# Build site for current package
/rforge:r:site

# Build and preview in browser
/rforge:r:site --preview

# CI-strict config check then build
/rforge:r:site --strict

# Rebuild only articles quickly
/rforge:r:site --articles-only

# Fast dev build (no install)
/rforge:r:site --devel
```

**Executes:**

- Validates config via `pkgdown_sitrep()` (or `check_pkgdown()` with `--strict`)
- Builds the site; needs `pandoc` to render vignettes
- If `pkgdown` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:document` (ensure Rd docs exist before building)

---

### /rforge:r:cycle

Full dev cycle — runs `document` → `test` → `check` in sequence, stopping at the first hard error.

**Usage:**

```bash
/rforge:r:cycle [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Full cycle for current package
/rforge:r:cycle
```

**Executes:**

- Runs `/rforge:r:document`, `/rforge:r:test`, `/rforge:r:check` in order
- Stops at first hard failure and reports the failing stage with detail
- Returns a stage-by-stage status table

**Related commands:** `/rforge:r:check`, `/rforge:r:test`, `/rforge:r:document`, `/rforge:thorough` (ecosystem rollup)

---

## R Quality

### /rforge:r:lint

Static analysis of the package via `lintr` — grouped report of style and code-quality issues.

**Usage:**

```bash
/rforge:r:lint [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Lint current package
/rforge:r:lint
```

**Executes:**

- Runs `lintr::lint_package()` (read-only; no files are changed)
- Groups findings by file with line numbers and lint rule names
- If `lintr` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:style` (auto-format fixes many style lints)

---

### /rforge:r:spell

Spell-check the package documentation via `spelling` and triage typos vs. technical terms.

**Usage:**

```bash
/rforge:r:spell [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Spell-check current package
/rforge:r:spell
```

**Executes:**

- Runs `spelling::spell_check_package()`
- Lists misspelled words with file and line location
- Recommends fixing real typos or adding technical terms to `inst/WORDLIST`
- If `spelling` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:check` (spelling NOTEs also surface in R CMD check)

---

### /rforge:r:urlcheck

Check package URLs for breakage and redirects via `urlchecker` — a common CRAN rejection cause.

**Usage:**

```bash
/rforge:r:urlcheck [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Check URLs in current package
/rforge:r:urlcheck
```

**Executes:**

- Runs `urlchecker::url_check()`
- Lists broken or redirected URLs with suggested replacements
- If `urlchecker` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:check` (broken URLs also flagged by R CMD check)

---

### /rforge:r:style

Auto-format the package source via `styler::style_pkg()` and show the diff.

**Usage:**

```bash
/rforge:r:style [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Style-format current package
/rforge:r:style
```

**Executes:**

- Runs `styler::style_pkg()` — **this rewrites files**
- Reports file count changed and shows `git diff --stat` summary
- Recommends `git diff` review and `git checkout -- <files>` if the changes are unwanted
- If `styler` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:lint` (find issues that styler does not auto-fix)

---

## CRAN Submission

### /rforge:r:revdep

Reverse-dependency check against CRAN downstream packages via `revdepcheck`.

**Usage:**

```bash
/rforge:r:revdep [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Check reverse dependencies for current package
/rforge:r:revdep

# Check specific package
/rforge:r:revdep ~/projects/medfit
```

**Executes:**

- Runs `revdepcheck::revdep_check()` — a hard CRAN obligation for API-changing updates
- Reports broken downstream packages and new problems
- `revdepcheck` is optional — if missing, reports 🟡 with install hint
- Note: can be slow (builds downstream packages)

**Related commands:** `/rforge:r:cran-prep` (runs revdep as part of the submission gate), `/rforge:deps` / `/rforge:impact` (internal ecosystem deps, not CRAN downstream)

---

### /rforge:r:goodpractice

Advisory best-practice bundle — goodpractice checks (opt-in, not part of `r:cycle`).

**Usage:**

```bash
/rforge:r:goodpractice [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Run advisory best-practice checks for current package
/rforge:r:goodpractice
```

**Executes:**

- Runs `goodpractice::gp()` — re-runs R CMD check, lintr, and covr plus additional checks (cyclomatic complexity, TODO/FIXME scan, DESCRIPTION completeness, etc.)
- Reports advisories with counts and descriptions
- `goodpractice` is optional — if missing, reports 🟡 with install hint
- Not part of `/rforge:r:cycle` to avoid double-running check/lint/coverage

**Related commands:** `/rforge:r:check`, `/rforge:r:lint`, `/rforge:r:coverage`, `/rforge:r:cran-prep`

---

### /rforge:r:winbuilder

Submit to win-builder (R-devel) via `devtools::check_win_devel()` — async dispatch.

**Usage:**

```bash
/rforge:r:winbuilder [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Dispatch to win-builder
/rforge:r:winbuilder
```

**Executes:**

- Submits the package to [win-builder](https://win-builder.r-project.org/) for a remote R-devel check on Windows
- **Async dispatch** — results are emailed to the DESCRIPTION Maintainer; nothing returns synchronously
- `devtools` is optional — if missing, reports 🟡 with install hint
- Run at least once per release after a clean `/rforge:r:check --as-cran` pass

**Related commands:** `/rforge:r:cran-prep` (runs winbuilder under `--multi-platform`), `/rforge:r:rhub`

---

### /rforge:r:rhub

Multi-platform checks via R-hub v2 (`rhub::rhub_check`) — async dispatch via GitHub Actions.

**Usage:**

```bash
/rforge:r:rhub [package]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)

**Examples:**

```bash
# Dispatch to R-hub v2
/rforge:r:rhub
```

**Executes:**

- Runs `rhub::rhub_check()` — triggers GitHub Actions workflows across Linux, macOS, Windows, and various R versions
- **Async dispatch** — results appear in the repo's Actions tab
- First run calls `rhub::rhub_setup()` (writes `.github/workflows/rhub.yaml`); subsequent runs skip setup
- A GitHub remote is required
- `rhub` is optional — if missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:cran-prep` (includes rhub under `--multi-platform`), `/rforge:r:winbuilder`

---

### /rforge:r:cran-prep

Per-package CRAN-readiness gate — runs the full pre-submission sequence and generates `cran-comments.md`.

**Usage:**

```bash
/rforge:r:cran-prep [package] [--goodpractice] [--multi-platform] [--no-revdep]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)
- `--goodpractice` (optional) - Also run the advisory goodpractice bundle (default: false)
- `--multi-platform` (optional) - Dispatch win-builder + R-hub async checks (default: false)
- `--no-revdep` (optional) - Skip the reverse-dependency check (default: false)

**Examples:**

```bash
# Full CRAN-prep gate for current package
/rforge:r:cran-prep

# Include goodpractice advisory and multi-platform checks
/rforge:r:cran-prep --goodpractice --multi-platform

# Skip revdep (e.g., first CRAN submission with no dependents)
/rforge:r:cran-prep --no-revdep
```

**Executes:**

- Full sequence: `document` → `lint` → `spell` → `urlcheck` → `test` → `coverage` → `check (--as-cran)` → `revdep`
- Generates `cran-comments.md` with a `ready` / `warn` / `blocked` verdict
- Returns a stage-by-stage status table; lists blockers that must be fixed before submission
- Composes with `/rforge:release` (this = single-package gate; release = cross-package submission ordering)

**Related commands:** `/rforge:release` (ecosystem-level submission ordering), `/rforge:r:revdep`, `/rforge:r:check`, `/rforge:r:winbuilder`, `/rforge:r:rhub`, `/rforge:r:cycle`

---

## Command Categories Summary

### By Time Budget

| Time | Commands |
|------|----------|
| <10s | `status`, `quick`, `detect`, `deps` (visual), `next` |
| <30s | `analyze` (default), `cascade`, `impact`, `docs:check` |
| <1min | `r:load`, `r:document`, `r:lint`, `r:spell`, `r:urlcheck`, `r:style` |
| <2min | `analyze` (debug/optimize), `r:test`, `r:coverage`, `r:build`, `r:install` |
| <5min | `thorough`, `analyze` (release), `r:check`, `r:site`, `r:cycle` |

### By Use Case

**Daily Development:**
- `/rforge:status` - Morning check-in
- `/rforge:next` - What to work on
- `/rforge:quick` - Pre-commit validation

**Feature Development:**
- `/rforge:analyze` - Check implementation impact
- `/rforge:impact` - Assess ecosystem effects
- `/rforge:complete` - Mark features done

**R Package Development:**
- `/rforge:r:load` - Load package into namespace
- `/rforge:r:document` - Regenerate Rd docs and NAMESPACE
- `/rforge:r:test` - Run testthat suite
- `/rforge:r:coverage` - Coverage gaps and untested lines
- `/rforge:r:cycle` - document → test → check in one pass

**R Quality Checks:**
- `/rforge:r:lint` - Static analysis (lintr)
- `/rforge:r:spell` - Spell-check docs
- `/rforge:r:urlcheck` - Validate URLs
- `/rforge:r:style` - Auto-format source (styler)

**Release Preparation:**
- `/rforge:analyze --mode release` - Full audit
- `/rforge:thorough` - Comprehensive checks
- `/rforge:release` - Plan submission order
- `/rforge:r:check` - R CMD check execution
- `/rforge:r:build` - Build source tarball
- `/rforge:r:site` - Build pkgdown website

**Ecosystem Management:**
- `/rforge:detect` - Understand structure
- `/rforge:deps` - Visualize dependencies
- `/rforge:cascade` - Plan coordinated updates
- `/rforge:health` - Overall metrics

## Global Flags

All analysis commands support:

**Mode flags:**
- `--mode default` - Quick analysis (<10s)
- `--mode debug` - Detailed diagnostics (<120s)
- `--mode optimize` - Performance focus (<180s)
- `--mode release` - Comprehensive audit (<300s)

**Format flags:**
- `--format terminal` - Rich colors and emojis (default)
- `--format json` - Machine-readable with metadata
- `--format markdown` - Documentation-ready

**Example:**
```bash
/rforge:analyze --mode release --format markdown > analysis.md
```

## See Also

- **[Quick Start Guide](quickstart.md)** - Getting started with RForge
- **[Architecture Guide](architecture.md)** - How RForge works
