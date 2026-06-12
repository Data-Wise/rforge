# 🔁 R package dev cycle with rforge

!!! tip "TL;DR (30 seconds)"
    - **What:** 12 `r:` commands that run the full R package development loop from inside Claude Code.
    - **Why:** One namespace, consistent JSON envelopes, no context-switching to a terminal.
    - **How:** Daily loop → `r:cycle`. Before committing → `r:lint` + `r:spell`. Before release → `r:coverage` + `r:urlcheck`. Build/deploy → `r:build` / `r:install` / `r:site`.
    - **Next:** [CRAN submission](cran-submission-with-rforge.md) for the pre-submission gate.

> **For whom:** R package developer who wants to run document/test/check and quality
> checks without leaving Claude Code.
> **Estimated time:** 10 minutes to read; commands themselves take seconds to minutes.
> **Prior knowledge:** You have an R package (a directory with a `DESCRIPTION` file)
> registered with `/rforge:init`.

## The two tiers

The 12 `r:` commands split into two tiers:

| Tier | Commands | Frequency |
|------|----------|-----------|
| **Dev cycle** — run constantly | `r:load`, `r:document`, `r:test`, `r:check`, `r:cycle` | Every code change |
| **Quality layer** — run before committing / releasing | `r:lint`, `r:spell`, `r:urlcheck`, `r:style`, `r:coverage`, `r:build`, `r:install`, `r:site` | Pre-commit / pre-release |

All commands default to the current directory. Pass a path to target a different package:

```bash
/rforge:r:test ~/projects/medfit
```

---

## Part 1: Daily dev cycle

### `r:cycle` — the one-liner

The fastest route for a full sanity check after any code change:

```bash
/rforge:r:cycle
```

Runs `document → test → check` in sequence, stopping at the first error.

```text
## Dev Cycle: medfit v2.0.0

| Stage    | Result |
|----------|--------|
| document | ✅     |
| test     | ✅     |
| check    | ✅     |

Status: 🟢 All stages passed
```

If a stage fails, the sequence stops and tells you exactly where:

```text
| Stage    | Result |
|----------|--------|
| document | ✅     |
| test     | ❌     |

Stopped at **test** — 2 failures, 0 errors
  • test-bootstrap.R:45: expected 0.42, got NA (missing seed?)
  • test-mediation.R:12: object 'indirect_ci' not found
```

!!! tip "r:cycle is the habit"
    Run it before every commit. If it's green, you're safe to push.
    If it's yellow (warnings), decide whether to fix now or note in NEWS.

---

### The individual stages

Use these when you want to zoom in on one stage without running the full cycle.

#### `r:load` — load the package into a namespace

```bash
/rforge:r:load
```

Runs `pkgload::load_all()`. Use after changing function signatures or exports — 
loads the package without installing it so tests can reach the new exports immediately.

```text
## Load: medfit v2.0.0
### Status: 🟢
Loaded medfit into the namespace.
```

!!! note "When to reach for r:load"
    You changed an exported function signature and want to test it interactively.
    `r:load` is faster than `r:install` for in-session exploration.

---

#### `r:document` — regenerate roxygen2 docs

```bash
/rforge:r:document
```

Runs `roxygen2::roxygenise()`. Regenerates `man/*.Rd` and `NAMESPACE`.

```text
## Document: medfit v2.0.0
### Status: 🟢
Generated 14 .Rd files, updated NAMESPACE.
```

!!! warning "Never hand-edit man/*.Rd"
    The rforge pre-tool hook blocks direct edits to `man/*.Rd`. Always
    edit the `#'` roxygen comments in `R/*.R` and re-run `r:document`.

---

#### `r:test` — run the test suite

```bash
/rforge:r:test
```

Runs `testthat::test_local()`. Reports pass/fail/skip/warning counts.

```text
## Tests: medfit v2.0.0
### Status: 🟢
| Passed | Failed | Skipped | Warnings |
|--------|--------|---------|----------|
| 187    | 0      | 2       | 0        |
```

When tests fail:

```text
### Status: 🔴
| Passed | Failed | Skipped | Warnings |
|--------|--------|---------|----------|
| 185    | 2      | 2       | 1        |

Failures:
  • test-bootstrap.R:45 — expected 0.42, got NA
  • test-mediation.R:12 — object 'indirect_ci' not found
```

---

#### `r:check` — run R CMD check

```bash
/rforge:r:check
```

Runs `rcmdcheck::rcmdcheck()`. For CRAN compliance, add `--as-cran`:

```bash
/rforge:r:check --as-cran
```

```text
## Package Check: medfit v2.0.0

| Errors | Warnings | Notes |
|--------|----------|-------|
| 0      | 0        | 1     |

Notes:
  • checking CRAN incoming feasibility ... NOTE
    New submission

Status: 🟡 (1 spurious NOTE — expected on first CRAN submission)
```

!!! tip "NOTEs are classified in v2.2.0+"
    `r:check` tags each NOTE as `spurious` (expected, e.g. "New submission")
    or `real` (needs attention). Spurious NOTEs are safe to ignore for CRAN.

---

## Part 2: Quality layer

Run these before committing or releasing. They're slower than the dev-cycle
commands and focus on long-term maintainability.

### `r:lint` — static analysis

```bash
/rforge:r:lint
```

Runs `lintr::lint_package()`. Reports style and potential bugs, grouped by file.

```text
## Lint: medfit v2.0.0
### Status: 🟡 (8 lints)

R/bootstrap.R
  :23 — object_name_linter: Variable 'bootStrap_Ci' should use snake_case
  :67 — line_length_linter: Line exceeds 80 characters

R/mediation.R
  :12 — assignment_linter: Use <- instead of =
```

`lintr` is optional — if missing, rforge reports 🟡 with an install hint.

---

### `r:style` — auto-fix style issues

```bash
/rforge:r:style
```

Runs `styler::style_pkg()`. **Writes** reformatted files — run `r:lint` after
to confirm lints are resolved.

```text
## Style: medfit v2.0.0
### Status: 🟢
3 files reformatted: R/bootstrap.R, R/mediation.R, R/utils.R
```

!!! tip "Workflow: r:style then r:lint"
    `r:style` fixes formatting (indentation, spacing, operator alignment).
    `r:lint` catches issues styler doesn't auto-fix (naming conventions, complexity).
    Run them in order: style first, then lint.

---

### `r:spell` — spell-check documentation

```bash
/rforge:r:spell
```

Runs `spelling::spell_check_package()`. Checks `.Rd` files and vignettes.

```text
## Spell Check: medfit v2.0.0
### Status: 🟡

Possible misspellings:
  • "bootstraped" (R/bootstrap.R:34) — did you mean "bootstrapped"?
  • "efficasy" (man/medfit.Rd:12) — did you mean "efficacy"?
```

!!! note "Technical terms and proper nouns"
    Add package-specific terms to `inst/WORDLIST` to suppress false
    positives. `spelling` checks that file automatically.

---

### `r:urlcheck` — validate URLs in documentation

```bash
/rforge:r:urlcheck
```

Runs `urlchecker::url_check()`. Validates all URLs in `.Rd` and `DESCRIPTION`.

```text
## URL Check: medfit v2.0.0
### Status: 🟡

⚠️ Redirects (update to final URL):
  • https://old-domain.org/paper → https://doi.org/10.1111/xxx
  • http://example.org → https://example.org (HTTP → HTTPS)

✅ 23 URLs OK
```

---

### `r:coverage` — test coverage report

```bash
/rforge:r:coverage
```

Runs `covr::package_coverage()`. Reports line coverage percentage.

```text
## Coverage: medfit v2.0.0
### Status: 🟢

Overall: 91.3%

| File            | Coverage |
|-----------------|----------|
| R/bootstrap.R   | 95.2%    |
| R/mediation.R   | 88.1%    |
| R/utils.R       | 100%     |

⚠️ Low coverage: R/mediation.R — consider adding tests for edge cases
```

`covr` is optional — if missing, rforge reports 🟡 with an install hint.

---

### `r:build` — build a source tarball

```bash
/rforge:r:build
```

Runs `pkgbuild::build()`. Produces the `.tar.gz` ready for `R CMD INSTALL` or CRAN upload.

```text
## Build: medfit v2.0.0
### Status: 🟢
Built: medfit_2.0.0.tar.gz (42 KB)
```

---

### `r:install` — install the package

```bash
/rforge:r:install
```

Runs `R CMD INSTALL`. Installs to your default R library.

```text
## Install: medfit v2.0.0
### Status: 🟢
Installed to /Library/Frameworks/R.framework/.../medfit
```

!!! note "r:load vs r:install"
    Use `r:load` for rapid in-session iteration (no disk install).
    Use `r:install` when you need the package available in a fresh R session
    or as a dependency of another package you're developing.

---

### `r:site` — build the pkgdown site

```bash
/rforge:r:site
```

Runs `pkgdown::build_site()`. Generates the HTML documentation site in `docs/`.

```text
## Site: medfit v2.0.0
### Status: 🟢
Built site → docs/index.html
  • 14 reference pages
  • 3 vignettes
  • Changelog
```

`pkgdown` is optional — if missing, rforge reports 🟡 with an install hint.

---

## Common workflows

### Before every commit

```bash
/rforge:r:cycle          # document → test → check (green = safe to push)
```

### Before a pull request

```bash
/rforge:r:cycle
/rforge:r:lint           # catch style issues
/rforge:r:spell          # catch doc typos
```

### Before a release

```bash
/rforge:r:cycle
/rforge:r:lint
/rforge:r:spell
/rforge:r:urlcheck
/rforge:r:coverage       # confirm coverage acceptable
/rforge:r:build          # confirm tarball builds clean
```

### Preparing for CRAN

Start here, then continue in [CRAN submission with rforge](cran-submission-with-rforge.md):

```bash
/rforge:r:cycle          # must be green first
/rforge:r:cran-prep      # full CRAN gate (runs everything + revdep)
```

---

## Optional engines

These `r:` commands use R packages that aren't installed by default:

| Command | R package | Install |
|---------|-----------|---------|
| `r:lint` | `lintr` | `install.packages("lintr")` |
| `r:spell` | `spelling` | `install.packages("spelling")` |
| `r:urlcheck` | `urlchecker` | `install.packages("urlchecker")` |
| `r:style` | `styler` | `install.packages("styler")` |
| `r:coverage` | `covr` | `install.packages("covr")` |
| `r:site` | `pkgdown` | `install.packages("pkgdown")` |

If any are missing, rforge reports 🟡 with the install hint — it never errors out.
Install them as you need them; `r:cycle` (document/test/check) has no optional deps.

---

## What's next

- **[CRAN submission with rforge](cran-submission-with-rforge.md)** — once
  `r:cycle` is green, run the full pre-submission gate with `r:cran-prep`
- **[CRAN release prep](cran-release-prep.md)** — ecosystem-level submission
  order when you have multiple interdependent packages
- **[REFCARD](../REFCARD.md)** — all {{ rforge.command_count }} commands in one page
