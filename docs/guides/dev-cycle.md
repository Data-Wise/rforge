# 🔁 Dev-cycle commands

!!! tip "TL;DR (30 seconds)"
    - **What:** The `r:` inner-loop commands — `load`, `document`, `test`, `check`,
      `coverage`, `build`, `install`, `site` — plus `cycle`, which runs
      `document → test → check` in one pass (stopping at the first hard error).
    - **Why:** This is the tight edit→verify loop you run dozens of times a day while
      developing an R package — *before* CRAN-submission gates or diff-aware merge gates.
    - **The family:** `load` · `document` · `test` · `check` · `coverage` · `build` ·
      `install` · `site` · `cycle`.
    - **Next:** [R package dev cycle](../tutorials/r-dev-cycle.md) for the task walkthrough.

> **For whom:** an R-package developer who wants the *full* behavior of the dev inner-loop
> command family — every flag, what each engine does, and which commands mutate files.
> **Prior knowledge:** an R package registered with `/rforge:init`; a working `Rscript`.

---

## What this family covers

These nine commands drive your **edit→verify** loop. Each one shells out to a single
lower-level R engine via `python3 -m lib.rcmd --kind <kind>` and normalizes the result to
one JSON envelope (see [`rcmd` reference](../reference/rcmd.md)). They are **single-package**:
they act on the package at the path you give (or the current directory). For
ecosystem-wide rollups use `/rforge:thorough` or `/rforge:health` instead.

| Command | One-line | Engine (lib.rcmd kind) |
|---------|----------|------------------------|
| `r:load` | Load the package into a namespace for dev | `load` → pkgload |
| `r:document` | Regenerate `man/*.Rd` + `NAMESPACE` | `document` → roxygen2 |
| `r:test` | Run the testthat suite (pass/fail/skip) | `test` → testthat |
| `r:check` | `R CMD check` with NOTE classification | `check` → rcmdcheck |
| `r:coverage` | Test coverage — total, per-file, gaps | `coverage` → covr |
| `r:build` | Build a source tarball | `build` → pkgbuild |
| `r:install` | Install the package locally | `install` → R CMD INSTALL |
| `r:site` | Build the pkgdown website | `site` → pkgdown |
| `r:cycle` | `document → test → check` in sequence | `cycle` (composite) |

!!! note "Read-only vs. mutating — and what auto-runs"
    `lib.rcmd` treats a subset of kinds as **SAFE_AUTORUN** (an agent or
    `/rforge:orchestrator` may run them without asking): `load`, `test`, `check`,
    `coverage`, `lint`, `spell`. The heavier or file-mutating kinds —
    **`document`** (rewrites `man/*.Rd` + `NAMESPACE`), **`build`** (writes a tarball),
    **`install`** (modifies your library), **`style`**, and **`site`** (writes `docs/`) —
    are recommended, never auto-run. `cycle` is composite: it *contains* `document`, so
    treat `cycle` as mutating too.

---

## `r:load` — load into a namespace

Simulate-installs the package into a fresh namespace via `pkgload::load_all()` so you can
call its functions interactively without a real install. **Read-only.**

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to load |

```bash
/rforge:r:load               # load the package in the current directory
/rforge:r:load path/to/pkg   # load a package elsewhere
```

Reports `🟢` + "Loaded {package} into the namespace." or surfaces the load error.

!!! tip "You rarely call this directly"
    `r:test` already self-loads via pkgload inside `test_local()`. Reach for `r:load` when
    you want an interactive namespace to poke at, not as a pre-test step.

---

## `r:document` — regenerate Rd + NAMESPACE

Runs `roxygen2::roxygenize()` to regenerate `man/*.Rd` and `NAMESPACE` from your roxygen
comments. **Mutating** — it rewrites generated files.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to document |

```bash
/rforge:r:document
git diff man/ NAMESPACE     # the recommended next step
```

!!! warning "This is the *blessed* regeneration path"
    The R-aware PreToolUse hook **blocks** hand-edits to `man/*.Rd` — those files are
    generated, not authored. Running roxygen through this command (a Bash invocation) is the
    allowed way to update them. Edit the roxygen comments above your functions, then re-run.

---

## `r:test` — run the testthat suite

Runs the suite via `testthat::test_local()` (which self-loads the package). **Read-only**
(SAFE_AUTORUN). Reports passed / failed / skipped / warning counts and lists failing files.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to test |
| `--changed` | boolean | `false` | Scope to package(s) changed on this branch; tag each failing-test finding `[introduced]` vs `[pre-existing]` |
| `--base` | string | `dev` | Comparison ref for `--changed` (diff + baseline run vs `merge-base(HEAD, base)`) |
| `--fail-on` | string | `introduced` | `--changed` exit policy: `introduced` fails iff ≥1 introduced finding; `none` is advisory |
| `--no-cache` | boolean | `false` | `--changed`: bypass the per-package baseline cache, force a fresh baseline |

```bash
/rforge:r:test                       # run the whole suite
/rforge:r:test --changed --base dev  # scope + tag vs the fork point (see diff-aware guide)
```

Output shape: `Passed` / `Failed` / `Skipped` / `Warnings` counts, plus a **Failing files**
list when there are failures.

!!! note "`--changed` / `--base` / `--fail-on` / `--no-cache` are the diff-aware flags"
    They scope the run to packages you touched and tag failures by origin. Their full
    behavior — the merge-base baseline, the `[uncommitted]` refinement, and the per-package
    cache — lives in the [diff-aware guide](diff-aware.md). Plain `r:test` ignores them.

---

## `r:check` — R CMD check, smartly parsed

Runs `R CMD check` via `rcmdcheck` and reports structured errors / warnings / notes. The
default is a single `--as-cran` pass. **Read-only** (SAFE_AUTORUN) — it builds in a temp dir
and never touches your source.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to check |
| `--as-cran` | boolean | `false` | Explicit `--as-cran` pass (this is already the default behavior) |
| `--strict` | boolean | `false` | Add both Suggests-withholding flavor passes (noSuggests + suggests-only) |
| `--incoming` | boolean | `false` | Implies `--strict`; adds a third CRAN-incoming pass |
| `--changed` | boolean | `false` | Scope to changed package(s) + tag findings `[introduced]` vs `[pre-existing]` |
| `--base` | string | `dev` | Comparison ref for `--changed` |
| `--fail-on` | string | `introduced` | `--changed` exit policy (`introduced` fails on regressions you caused; `none` advisory) |
| `--no-cache` | boolean | `false` | `--changed`: force a fresh merge-base baseline (skip the cache) |

```bash
/rforge:r:check              # single --as-cran pass (the default)
/rforge:r:check --as-cran    # explicit, same thing
```

Output shape: error / warning / note counts, then a **NOTE classification** block —
each NOTE is tagged `🟢 expected` (spurious) or `🔴 needs attention` (real) — and recommended
actions.

!!! note "`--strict` / `--incoming` and `--changed` exist here, but live in other guides"
    - **`--strict` / `--incoming`** add CRAN-grade Suggests-withholding and incoming passes —
      a pre-*submission* gate, not part of the inner loop. See the
      [CRAN submission guide](cran-submission.md). (Behavior change: a package green under
      `--as-cran` can turn red under `--strict` if it uses a `Suggests` package
      unconditionally — that's intended.)
    - **`--changed` / `--base` / `--fail-on` / `--no-cache`** scope and tag findings vs the
      fork point — a merge gate. See the [diff-aware guide](diff-aware.md).

    This page covers only the **plain** `r:check` you run while developing.

---

## `r:coverage` — what the tests miss

Computes coverage via `covr::package_coverage()` plus `zero_coverage()` for the gaps.
**Read-only** (SAFE_AUTORUN). `covr` is optional — if missing, you get `🟡` + an install hint
rather than an error.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to measure |

```bash
/rforge:r:coverage
```

Output shape: total `%`, the **lowest-covered files** (top 5 ascending), and **untested
lines** as ranges (e.g. `R/foo.R:12-18`) so you know exactly where to add tests.

---

## `r:build` — build a source tarball

Builds a source tarball via `pkgbuild::build()`. **Mutating** — it produces a `.tar.gz`
artifact on disk.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to build |

```bash
/rforge:r:build
```

Output shape: `🟢/🔴`, the artifact path, and its size in KB.

---

## `r:install` — install locally

Installs the package via `R CMD INSTALL`. **Mutating** — it modifies your R library.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to install |

```bash
/rforge:r:install
```

Output shape: `🟢 exit 0 / 🔴`, the installed version, and (on error) surfaced messages such
as unmet dependencies.

!!! tip "build → install for a clean-room check"
    `r:build` then `r:install` mirrors how a user would receive the package. For day-to-day
    work, `r:load` is faster (no real install).

---

## `r:site` — build the pkgdown website

Validates (`pkgdown_sitrep`, or `check_pkgdown` with `--strict`) then builds the pkgdown
site, turning vignettes into articles. **Mutating** — it writes the rendered site to `docs/`.
`pkgdown` is optional (missing → `🟡` + hint); rendering vignettes needs `pandoc` (missing →
`🟡` + hint).

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to build the site for |
| `--preview` | boolean | `false` | Open the built site (`pkgdown::preview_site`) |
| `--strict` | boolean | `false` | Fail-fast config check (`check_pkgdown`) for CI |
| `--articles-only` | boolean | `false` | Build only articles/vignettes (reinstalls first) |
| `--devel` | boolean | `false` | Fast in-process build via `load_all` (lower fidelity) |

```bash
/rforge:r:site                  # validate + full build
/rforge:r:site --preview        # build, then open it
/rforge:r:site --strict         # fail-fast config check for CI
/rforge:r:site --articles-only  # rebuild just the vignettes (reinstalls first)
/rforge:r:site --devel          # quick in-process build while iterating
```

Output shape: `🟢 built clean / 🟡 built with problems / 🔴 build failed`, what was checked
vs built, vignette/render errors on failure, and config/index problems (bad URLs,
un-indexed topics).

!!! warning "`--articles-only` reinstalls first"
    It installs the current source before rebuilding articles, so it is **not** a free
    shortcut — it's the right flag when an article depends on the latest package code. For
    pure iteration speed, prefer `--devel` (in-process, lower fidelity).

---

## `r:cycle` — document → test → check, in one pass

Runs `document → test → check` **in sequence, stopping at the first hard error**. It's the
fast "did I break anything?" sweep. **Mutating** — it includes `document`, which rewrites
`man/*.Rd` + `NAMESPACE`.

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `package` | string | current dir | Package path to run the cycle on |

```bash
/rforge:r:cycle
```

Output shape: an overall status plus a per-stage table:

| Stage | Result |
|-------|--------|
| document | 🟢 |
| test | 🟢 |
| check | 🟡 |

If a stage fails, the run **stops** and reports `Stopped at **{stage}**` with the failure
detail — so a `document` failure never wastes time running `test` and `check`.

!!! tip "Run `r:cycle` before you commit"
    It catches the three most common pre-commit regressions — stale docs, broken tests, a
    failing check — in one command. When it's green, reach for the diff-aware `--changed`
    flags (per-command) to gate the *merge*.

---

## See also

- [Command reference](../commands.md) — terse one-liners + the full flag tables for every command
- [`rcmd` reference](../reference/rcmd.md) — the `lib.rcmd` engine these commands drive (kinds, envelope, `run_changed`)
- [R package dev cycle](../tutorials/r-dev-cycle.md) — the task walkthrough for this inner loop
- [Diff-aware checks](diff-aware.md) — `--changed` / `--base` / `--fail-on` depth for `check` / `test`
- [CRAN submission](cran-submission.md) — `--strict` / `--incoming` and the full pre-submission gate
