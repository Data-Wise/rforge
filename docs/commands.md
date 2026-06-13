# 📖 RForge Commands Reference

!!! tip "TL;DR (30 seconds)"
    - **What:** Full per-command reference (parameters, examples, output format).
    - **Why:** REFCARD is a cheat sheet; this page is the deep dive.
    - **How:** Jump to a category below, or `Ctrl+F` for a specific command.
    - **Next:** [REFCARD](REFCARD.md) for the at-a-glance summary.

Complete reference for all **{{ rforge.command_count }}** RForge commands. Commands are organized by category with usage examples and parameter details.

## Command Categories

- [Setup & State](#setup-state) (1 command)
- [Status & Analysis](#status-analysis) (4 commands)
- [Ecosystem Management](#ecosystem-management) (6 commands)
- [Documentation & Tasks](#documentation-tasks) (4 commands)
- [Health Checks](#health-checks) (2 commands)
- [R Development Cycle](#r-development-cycle) (8 commands)
- [R Quality](#r-quality) (5 commands)
- [CRAN Submission](#cran-submission) (6 commands)
- [R Authoring](#r-authoring) (5 commands)

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
- **Role column + manifest drift (v2.4.0)** — when an ecosystem manifest is configured via
  `.rforge.yaml` `manifest:`, the dashboard adds a conditional `Role` column (from the manifest)
  and a drift block. Without a manifest, the dashboard is unchanged.

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

**Ecosystem manifest (v2.4.0):** if the root `.rforge.yaml` declares a `manifest:` path,
`/rforge:detect` reads that ecosystem manifest, shows a `manifest:` header field and a per-package
`role`, and reports **drift** (packages in the manifest but not on disk, and vice-versa). Add the
field to `.rforge.yaml` as `manifest: <relative-path-to.yaml>`; with no manifest configured, output
is unchanged.

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

### /rforge:r:deps-sync

Reconcile **one package's** `DESCRIPTION` against what its code actually uses (the *intra*-package
counterpart to `/rforge:deps`, which maps the *inter*-package graph). Pure-Python — scans
`R/`/`tests/`/`vignettes/` + `NAMESPACE`.

**Usage:**
```bash
/rforge:r:deps-sync [package] [--write]
```

**Parameters:**
- `package` (optional) — package path (defaults to current directory)
- `--write` (optional) — apply the unambiguous `Imports`/`Suggests` changes to `DESCRIPTION` (default is report-only)

**Findings:** `missing` (used, undeclared → Imports), `misclassified` (in Suggests but used
unconditionally in `R/` → Imports — the static sibling of `r:check --strict`'s noSuggests pass),
`missing_suggests` (tests/vignettes-only → Suggests), `unused` (declared, no usage — advisory).
Emits a suggested patch; `--write` applies only the unambiguous parts (advisory removals are never
auto-applied).

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
/rforge:r:check [package] [--strict] [--incoming] [--changed] [--base <ref>] [--changed-strict]
```

**Parameters:**
- `package` (optional) - Package to check (defaults to current)
- `--strict` (optional) - Run both CRAN Suggests-withholding flavors (default: false)
- `--incoming` (optional) - Emulate CRAN's incoming `_R_CHECK_*` bundle; implies `--strict` (default: false)
- `--changed` (optional, v2.10.0; tagging v2.11.0) - Scope the check to the package(s) changed on this branch and tag each finding **`[introduced]`** (new on your branch) vs **`[pre-existing]`** (already at the fork point), via a baseline run in a detached worktree at `merge-base(HEAD, --base)` (default: false)
- `--base <ref>` (optional, v2.11.0) - Comparison ref for `--changed`; the baseline is run at `merge-base(HEAD, base)` (default: `dev`)
- `--fail-on <introduced|none>` (optional, v2.11.0) - Exit non-zero only on findings tagged `[introduced]` (default: `introduced`); `none` is advisory
- `--changed-strict` (optional, v2.10.0) - Documented no-op (default: false)

**Examples:**
```bash
# Check current package (single --as-cran pass)
/rforge:r:check

# Check specific package
/rforge:r:check mypackage

# Strict CRAN-incoming check (both Suggests flavors)
/rforge:r:check --strict

# Add the opt-in incoming env-var bundle
/rforge:r:check --incoming

# Tag findings [introduced]/[pre-existing] vs the fork point; fail only on introduced
/rforge:r:check --changed --base dev
```

**Executes:**
- R CMD check with `--as-cran` flags
- Parses output for errors/warnings/notes
- Categorizes issues (NOTEs classified as `spurious` vs `real`)
- Suggests fixes

**Strict mode (v2.3.0):** `--strict` runs **two additional flavor passes** as distinct stage rows — `check (noSuggests)` (`_R_CHECK_DEPENDS_ONLY_=true`) and `check (suggests-only)` (`_R_CHECK_SUGGESTS_ONLY_=true`), each with `--run-donttest`. These catch the error classes CRAN's post-acceptance flavors detect but a plain `--as-cran` run misses. `--incoming` implies `--strict` and adds a third `check (incoming)` row.

!!! warning "Behavior change in v2.3.0"
    A package that passes the default `--as-cran` check today can fail `--strict` once the **noSuggests** pass catches a `Suggests` package used unconditionally (the medfit 0.2.1 class — `MASS::mvrnorm` in a default code path). This is intended: CRAN would bounce such a package post-acceptance. Move the dependency to `Imports`, or guard it with `requireNamespace()` in code and `skip_if_not_installed()` in tests.

**Note:** This can take 1-5 minutes depending on package size. Strict mode runs the baseline plus two flavor passes (~3× check time; ~4× with `--incoming`).

**Diff-aware mode (v2.10.0; tagging v2.11.0):** `--changed` scopes the check to the R package(s) touched on this branch and tags each finding **`[introduced]`** vs **`[pre-existing]`** — computed honestly by a second baseline run in a detached worktree checked out at `merge-base(HEAD, --base)` (default base `dev`). `--fail-on introduced` (the default) exits non-zero only on findings your branch introduced, so CI fails on regressions you caused — not pre-existing debt (`--fail-on none` is advisory). Identity is line-shift-immune (findings key on file + message, not raw line). Degrades gracefully: not a git repo / no merge-base / baseline-worktree failure → falls back to a real full check plus a warning (scope-only, no tagging — no regression of v2.10.0); no changes → a clean no-op. Out of scope: uncommitted-change tagging and cross-run baseline caching (each invocation pays one extra check). `--changed-strict` is a documented no-op.

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
/rforge:r:test [package] [--changed] [--base <ref>]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)
- `--changed` (optional, v2.10.0; tagging v2.11.0) - Scope tests to the package(s) changed on this branch and tag findings `[introduced]`/`[pre-existing]` via a merge-base baseline run (default: false)
- `--base <ref>` (optional, v2.11.0) - Comparison ref for `--changed` (default: `dev`)
- `--fail-on <introduced|none>` (optional, v2.11.0) - Exit non-zero only on `[introduced]` findings (default: `introduced`)

**Examples:**

```bash
# Test current package
/rforge:r:test

# Test only packages changed on this branch
/rforge:r:test --changed --base dev
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
/rforge:r:lint [package] [--changed] [--base <ref>]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)
- `--changed` (optional, v2.10.0; tagging v2.11.0) - Scope lint to the package(s) changed on this branch and tag findings `[introduced]`/`[pre-existing]` via a merge-base baseline run; line-shift-immune identity (default: false)
- `--base <ref>` (optional, v2.11.0) - Comparison ref for `--changed` (default: `dev`)
- `--fail-on <introduced|none>` (optional, v2.11.0) - Exit non-zero only on `[introduced]` findings (default: `introduced`)

**Examples:**

```bash
# Lint current package
/rforge:r:lint

# Lint only packages changed on this branch
/rforge:r:lint --changed --base dev
```

**Executes:**

- Runs `lintr::lint_package()` (read-only; no files are changed)
- Groups findings by file with line numbers and lint rule names
- If `lintr` is missing, reports 🟡 with install hint

**Related commands:** `/rforge:r:style` (auto-format fixes many style lints)

---

### /rforge:r:s7-review

Static **S7 OOP convention checker** — scans `R/*.R` + `NAMESPACE` and reports advisory convention findings across five static families. **Advisory only, never blocks** (mirrors `r:cran-prep`'s Tier-4 tone). The static pass is pure Python — no R, no Rscript. An opt-in `--runtime` pass adds two R-backed families (loads the package and introspects S7 at runtime), and `--eco` sweeps the static families across the whole ecosystem manifest.

**Usage:**

```bash
/rforge:r:s7-review [package] [--kind all|naming|validators|methods|legacy|docs] [--eco] [--runtime] [--format json|text]
```

**Parameters:**

- `package` (optional, positional) - Package directory to review (defaults to current directory)
- `--kind` (optional) - Limit to one convention family: `all` (default), `naming`, `validators`, `methods`, `legacy`, or `docs`
- `--eco` (optional) - Sweep the static families across **every package** in the ecosystem manifest, aggregated (pure-stdlib; composes with `--runtime`)
- `--runtime` (optional) - Add an R-backed runtime pass (`method-dispatch` + `validator-runtime`) via `lib.rcmd`; degrades to an advisory `warn` when R/S7 is unavailable
- `--format` (optional) - Output format: `json` (default) or `text`

There is **no** `--write`/`--fix` — S7 fixes need human judgement.

**Examples:**

```bash
# Review all S7 conventions in the current package
/rforge:r:s7-review

# Only the naming family, as text
/rforge:r:s7-review --kind naming --format text

# Review a specific package
/rforge:r:s7-review ~/projects/mypackage

# Sweep the whole ecosystem (static families)
/rforge:r:s7-review --eco

# Add the R-backed runtime pass (dead generics + non-enforcing validators)
/rforge:r:s7-review --runtime
```

**Convention families:**

| Family | Example codes | Source |
|---|---|---|
| naming | `class_name_case`, `class_name_mismatch`, `generic_name_case`, `prop_name_case` | static |
| validators | `missing_validator`, `validator_return_shape` | static |
| methods | `dangling_method`, `missing_methods_register` | static |
| legacy | `legacy_s4_in_s7`, `legacy_r5_in_s7`, `legacy_s3_generic` | static |
| docs | `undocumented_export`, `prop_type_unresolvable` | static |
| method-dispatch (`--runtime`) | `dead_generic`, `method_on_missing_class` | runtime |
| validator-runtime (`--runtime`) | `validator_not_enforcing` | runtime |

The `method-dispatch` runtime family reports `dead_generic` (an S7 generic with no registered method) and `method_on_missing_class` (a method whose dispatch signature references an S7 class with no resolvable namespace binding — e.g. an inline `new_class()` left in a `method()` call — making the method unreachable). Each `S7_method` carries its dispatch class objects (`attr(., "signature")`), so resolvability is decided by object identity against the package's classes; base types and imported classes are not flagged.

**Output:** one `{kind: "s7review", status: "ok"|"warn", stages: [...]}` envelope. Each finding carries `source: "static"` and `severity: "advisory"`, worded "looks like / consider", never "must". Exit 0 always.

**Related commands:** `/rforge:r:cran-prep` (Tier-4 advisory siblings), `/rforge:r:document`

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
/rforge:r:cran-prep [package] [--incoming] [--goodpractice] [--multi-platform] [--no-revdep]
```

**Parameters:**

- `package` (optional) - Package path (defaults to current directory)
- `--incoming` (optional) - Also run the opt-in CRAN-incoming `_R_CHECK_*` pass (default: false)
- `--goodpractice` (optional) - Also run the advisory goodpractice bundle (default: false)
- `--multi-platform` (optional) - Dispatch win-builder + R-hub async checks (default: false)
- `--no-revdep` (optional) - Skip the reverse-dependency check (default: false)

**Examples:**

```bash
# Full CRAN-prep gate for current package (strict passes run by default)
/rforge:r:cran-prep

# Add the opt-in incoming env-var pass
/rforge:r:cran-prep --incoming

# Include goodpractice advisory and multi-platform checks
/rforge:r:cran-prep --goodpractice --multi-platform

# Skip revdep (e.g., first CRAN submission with no dependents)
/rforge:r:cran-prep --no-revdep
```

**Executes:**

- Full sequence: `document` → `lint` → `spell` → `urlcheck` → `test` → `coverage` → `check` → strict + Tier 4 stages → `revdep`
- The `check` stage now expands into multiple rows: `check`, `check (noSuggests)`, `check (suggests-only)`, (with `--incoming`) `check (incoming)`, then the Tier 4 advisory stages `description`, `build-hygiene`, and `docs-consistency`
- **Strict passes run by default** (v2.3.0): `check (noSuggests)` + `check (suggests-only)`, each with `--run-donttest`. A strict **ERROR blocks the `ready` verdict** (catches the medfit-class Suggests misuse). Plus a Tier 1b PDF-manual check (warns, never blocks if no LaTeX).
- **Tier 4 (advisory, NEVER blocks `ready`)** — three stages backed by `lib/cranlint.py` (pure Python, no R): `description` (DESCRIPTION incoming nits — non-`Authors@R`, weak `Title`, `Description` prose, stale `Date`), `build-hygiene` (planning/dev docs that would ship in the tarball, with the exact `.Rbuildignore` regex to add), `docs-consistency` (lightweight advisory). Build-hygiene findings still block indirectly via the matching real R CMD check NOTE once R runs.
- Generates `cran-comments.md` with a `ready` / `warn` / `blocked` verdict
- Returns a stage-by-stage status table; lists blockers that must be fixed before submission
- Composes with `/rforge:release` (this = single-package gate; release = cross-package submission ordering)

!!! warning "Behavior change in v2.3.0"
    Because the strict passes run by default and block `ready`, a package that reports 🟢 `ready` today under `--as-cran` can turn 🔴 `blocked` once the noSuggests pass catches an unconditional `Suggests` use. Intended — CRAN would bounce it post-acceptance. The fix: move the package to `Imports`, or guard with `requireNamespace()` + `skip_if_not_installed()`.

**Related commands:** `/rforge:release` (ecosystem-level submission ordering), `/rforge:r:revdep`, `/rforge:r:check`, `/rforge:r:winbuilder`, `/rforge:r:rhub`, `/rforge:r:cycle`, `/rforge:r:submit`

---

### /rforge:r:submit

GitHub pre-release of the submitted tarball + CRAN submit **handoff** — fills the gap between
`r:cran-prep` (reports `ready`) and CRAN going live. **Never auto-submits to CRAN.**

**Usage:**

```bash
/rforge:r:submit [package] [--promote] [--universe] [--universe-name <owner>] [--dry-run] [--no-verify] [--force]
```

**Parameters:**

- `package` (optional) — package path (defaults to current directory)
- `--promote` (optional) — Phase 2: flip the pre-release to a full release after CRAN accepts
- `--universe` (optional) — Phase 0: also verify the package's **R-universe early-access** build is green (read-only; never uploads). Advisory — never blocks the CRAN handoff.
- `--universe-name <owner>` (optional) — override the auto-detected R-universe owner (defaults to the GitHub `origin` remote owner)
- `--dry-run` (optional) — show the tag/assets/checklist without touching GitHub
- `--no-verify` (optional) — with `--promote`, skip the `cran.r-project.org` version check
- `--force` (optional) — cut the pre-release even if `cran-prep` is not `ready` (records the override)

**Lifecycle:**

- **Phase 0** (`r:submit --universe`, optional): verify the **R-universe early-access** build.
  R-universe rebuilds the package from its GitHub repo within minutes and serves CRAN-like binaries,
  so users can `install.packages("<pkg>", repos = "https://<owner>.r-universe.dev")` **while** CRAN
  review runs. Auto-detects the universe from the git `origin` remote, reads the public R-universe
  API, and reports per-platform build status. **Read-only** — R-universe builds on `git push`, so it
  never uploads. Backed by pure-stdlib `lib/runiverse.py` (`urllib`-only; no `gh`/R); degrades to a
  `warn` envelope offline/unregistered (with one-time setup guidance), never blocking the steps below.
- **Phase 1** (`r:submit`): gate on `cran-prep` = `ready` → build the tarball (reuse `r:build`) → cut a
  GitHub **pre-release** (not "Latest") tagged `v<version>` with `cran-comments.md` + tarball attached →
  print the CRAN submit checklist for you to run (with an **advisory** R-universe status line).
- **Phase 2** (`r:submit --promote`): optionally verify the version is live on CRAN, then
  `gh release edit v<version> --prerelease=false --latest`.

Uses a *pre-release promoted in place* to avoid tagging a final release before acceptance (resubmissions
bump the version — the r-pkgs anti-pattern). `gh` is a soft dependency: if absent/unauthed, the command
prints the manual `gh` recipe instead of failing. Backed by `lib/ghrelease.py` (release commands) and
`lib/runiverse.py` (R-universe status).

**Related commands:** `/rforge:r:cran-prep` (upstream gate), `/rforge:r:build` (the tarball), `/rforge:release`

---

## R Authoring

Scaffolding commands for **existing** packages. All three are **dry-run by default** — they print the plan and write nothing; pass `--write` to apply and `--force` to overwrite. They never invent expected values or docs prose; generated bodies are left as `# TODO` for you to fill.

### /rforge:r:use-test

Scaffold `tests/testthat/test-<function>.R` for an existing function and draft a `test_that()` block per branch — happy path, one per `stop()`, one per constrained `@param`. **No oracle:** assertions are emitted as `# TODO` (the engine never invents expected values).

**Usage:**

```bash
/rforge:r:use-test <function> [--write] [--force]
```

**Parameters:**

- `function` (required) - The exported function to scaffold tests for (one per call)
- `--write` (optional) - Apply the plan: create the file (sets up testthat 3e infra if absent). Default is dry-run (default: false)
- `--force` (optional) - Overwrite an existing test file, diff shown first (default: false)

**Examples:**

```bash
# Dry-run: print the planned file, write nothing
/rforge:r:use-test my_function

# Apply: create the test file
/rforge:r:use-test my_function --write

# Overwrite an existing file
/rforge:r:use-test my_function --write --force
```

After `--write`, fill each `# TODO` with a real expected value verified against documented behavior, then run `/rforge:r:test`.

**Related commands:** `/rforge:r:test`, `/rforge:r:coverage`, `/rforge:r:document`

---

### /rforge:r:use-package

Declare a single dependency for an existing package. The `Imports`-vs-`Suggests` decision reuses `lib/deps_sync.py`'s usage scan (unconditional `R/` use → **Imports**; tests/vignettes or guarded only → **Suggests**); the `DESCRIPTION` edit reuses the same DCF writer as `/rforge:r:deps-sync`. For an Imports dep, an `#' @importFrom <pkg> <symbol>` is inserted.

**Usage:**

```bash
/rforge:r:use-package <package> [--write] [--force]
```

**Parameters:**

- `package` (required) - The dependency to declare (one per call)
- `--write` (optional) - Apply the change to `DESCRIPTION` + the `@importFrom`. Default is dry-run (default: false)
- `--force` (optional) - Reserved for symmetry with the other `use-*` commands (default: false)

**Examples:**

```bash
# Dry-run: show the field decision + planned DESCRIPTION/@importFrom edits
/rforge:r:use-package rlang

# Apply: write DESCRIPTION + insert @importFrom
/rforge:r:use-package rlang --write
```

The recommendation + reason is always surfaced so you can override it. After `--write` on an Imports dep, run `/rforge:r:document` to regenerate `NAMESPACE`.

**Related commands:** `/rforge:r:deps-sync` (reconcile all deps at once), `/rforge:r:document`, `/rforge:r:check --strict`

---

### /rforge:r:use-vignette

Scaffold `vignettes/<name>.Rmd` for an existing package: a knitr skeleton (YAML index entry + engine) plus a drafted outline seeded from the package Title/Description. Section bodies are `# TODO`.

**Usage:**

```bash
/rforge:r:use-vignette <name> [--article] [--write] [--force]
```

**Parameters:**

- `name` (required) - The vignette file name (becomes `vignettes/<name>.Rmd`)
- `--article` (optional) - Create a pkgdown-only article (not built/installed) instead of a vignette (default: false)
- `--write` (optional) - Apply the plan: write the `.Rmd` and register the `VignetteBuilder` via guarded `usethis`. Default is dry-run (default: false)
- `--force` (optional) - Overwrite an existing vignette file, diff shown first (default: false)

**Examples:**

```bash
# Dry-run: print the planned .Rmd, write nothing
/rforge:r:use-vignette intro

# Apply: write the .Rmd, then register the builder
/rforge:r:use-vignette intro --write

# Create a pkgdown-only article instead
/rforge:r:use-vignette advanced --article --write
```

If `usethis` is absent, a manual `usethis::use_vignette()` recipe is printed (non-fatal — the `.Rmd` is still written).

**Related commands:** `/rforge:r:site` (build vignettes → articles), `/rforge:r:check`

---

### /rforge:r:use-data

Document a package dataset for an existing package: appends a roxygen doc stub to `R/data.R` (`@title`, `@format` with a `\describe{}` skeleton, `@source`, and the trailing `"<name>"` documented-data idiom) and patches `DESCRIPTION` (`LazyData: true` / `Depends: R (>= 2.10)`). Never fabricates the `.rda` — emits a `usethis::use_data(<name>)` reminder. DESCRIPTION edits preserve existing version constraints.

**Usage:**

```bash
/rforge:r:use-data <name> [--write]
```

**Parameters:**

- `name` (required) - The dataset/object name to document
- `--write` (optional) - Apply the plan: append to `R/data.R` (create if absent) + patch DESCRIPTION. Default is dry-run (default: false)

**Examples:**

```bash
# Dry-run: print the planned roxygen block + DESCRIPTION delta
/rforge:r:use-data mydata

# Apply: append the doc + patch DESCRIPTION
/rforge:r:use-data mydata --write
```

A collision guard skips appending if `R/data.R` already documents the same `\name` (warns, no duplicate).

**Related commands:** `/rforge:r:document` (regenerate the Rd), `/rforge:r:check`

---

### /rforge:r:use-citation

Scaffold `inst/CITATION` from `DESCRIPTION`: parses `Title`, `Authors@R` (or fallback `Author`), and `Version`, and renders a `bibentry(bibtype = "Manual", ...)` using the package's own `person()` calls. The year comes from `Date:` if present, else a `<YEAR>` TODO — never a wall-clock date (determinism). Unparseable authors degrade to a `# TODO` block + a warning.

**Usage:**

```bash
/rforge:r:use-citation [--write] [--force]
```

**Parameters:**

- `--write` (optional) - Apply the plan: write `inst/CITATION` (create `inst/` if absent). Default is dry-run (default: false)
- `--force` (optional) - Overwrite an existing `inst/CITATION` (refused without this flag) (default: false)

**Examples:**

```bash
# Dry-run: print the planned inst/CITATION
/rforge:r:use-citation

# Apply: write inst/CITATION
/rforge:r:use-citation --write

# Overwrite an existing inst/CITATION
/rforge:r:use-citation --write --force
```

**Related commands:** `/rforge:r:check` (validates `inst/CITATION` parses)

---

## Command Categories Summary

### By Time Budget

| Time | Commands |
|------|----------|
| <10s | `status`, `quick`, `detect`, `deps` (visual), `next`, `r:s7-review`, `r:use-test`/`r:use-package`/`r:use-vignette`/`r:use-data`/`r:use-citation` (dry-run) |
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
